# Public deployment on Vercel, Modal and MongoDB Atlas

- Status: draft
- Date: 2026-10-20
- Source baseline: `e0ac45c` on `claude-chat-backend` (branch `modal-deployment`)
- Request: deploy publicly with "option 1": Vercel, Modal for PyTorch and Optuna, Claude
  for the agent (repository owner, October 20)
- Human reviewer/approval: pending
- Independent review: required for the lock and dispatch changes (concurrency); a
  different-vendor reviewer is unavailable, so a disclosed same-vendor review is planned

## Proposed behavior and purpose

Anyone with the link opens the dashboard on Vercel and can upload a CSV, train, tune,
chat with Claude and download verified models. Nothing has to be kept switched on:

- the dashboard is static files on Vercel;
- the API and training run on Modal only while requests or jobs are active;
- records are kept in MongoDB Atlas;
- the agent uses the Claude API.

The Docker Compose, Kubernetes and CI setup stays in the repository unchanged as the
course deliverable. This is an additional deployment target, not a replacement.

## Clarification and critique

Facts from source (code map, October 20; references in the review notes):

- **Jobs are dispatched through Celery and Redis.** `queue.py` sends `train`/`tune` to
  Redis. A Celery worker runs `execution.py`/`tuning_execution.py`. A Celery beat
  scheduler re-dispatches lost or expired jobs every 15 s (`worker.py:40`). The
  readiness check pings Redis.
- **The API reads and writes local disk** for:
  - dataset registration, upload, preview and prepare;
  - column edits;
  - artifact download;
  - model-version registration;
  - deletion.

  Workers write checkpoints to that same disk. Atomic publication uses `os.link` and
  `os.replace`.
- **Coordination uses native file locks.** `storage_control.py` uses `FileLock` with
  `fallback_to_soft=False` for per-attempt and publication locks, and deletion takes
  every lock.
- **Jobs run up to ~10.5 minutes.** Training is capped at 600 s and tuning at 600 s
  with 50 trials, plus a 630 s hard limit.
- **Monitoring** embeds Grafana from a hard-coded `http://127.0.0.1:3000`.
  Prometheus scrapes without an API key.

Case against the requested shape (API as Vercel functions):

- A Vercel function has no disk it can share with Modal, so every file route would
  need rewriting onto object storage, plus a new lock design.
- Vercel's function request-body limit (about 4.5 MB) is below the 10 MB upload limit.

That is the largest and riskiest version of this change.

Recommended shape (implementer's proposal; **the owner must choose**, see Q1):

- Run the existing FastAPI app on **Modal** as a web endpoint, with a **Modal Volume**
  mounted as `dataset_root` and `artifact_root`.
- Run training and tuning as Modal functions on the same Volume.
- **Vercel** serves the static dashboard and forwards `/api/*` to the Modal URL. The
  browser stays same-origin, so CORS and the dashboard's request code stay unchanged.

Only the coordination layer needs new code: dispatch, recovery and locks.

Simpler alternatives considered:

- One small always-on server running Docker Compose: no code changes, but the owner
  chose not to keep a server running.
- Rewriting training into scikit-learn inside Vercel: rejected earlier, because it
  drops PyTorch and is limited by Vercel's timeouts.

### Questions for the owner

1. **Where does the API run?**
   - **(a) Modal API + Vercel dashboard (recommended):** least code change; uploads keep
     the 10 MB limit.
   - **(b) API as Vercel functions:** as on the slides; needs object storage (for
     example Cloudflare R2 or S3), MongoDB-based locks for every file route, and
     uploads capped below about 4.5 MB.
2. **Accounts.** You need Vercel, Modal and MongoDB Atlas accounts (all have free
   tiers). You must log in yourself (`modal token new`, `vercel login`) and create the
   Atlas cluster. Do you already have any of them?
3. **Monitoring on the public site.** Either drop the Grafana panels there (they show
   "unavailable" and the measured summary still works), or connect Grafana Cloud later
   in its own plan. The proposal is to drop them for now.
4. **Spending limits.** Modal bills per second with monthly free credits, and Claude
   bills per request. Is a hard cap wanted, such as one training container at a time
   and a Claude per-day request limit?

## Requirements

| ID | Type | Requirement | Acceptance evidence |
| --- | --- | --- | --- |
| F1 | Functional | On the public URL: upload → prepare → train → view result → download verified artifact → register version → chat with Claude, as locally. | Scripted smoke test against the deployed URL plus a browser walkthrough with screenshots. |
| F2 | Functional | Training and tuning run on Modal with the existing claim, lease, heartbeat, attempt and fencing rules. Tuning keeps its MongoDB transaction fence. | Existing worker and tuning tests pass with the Modal dispatcher. New tests cover spawn failure → `queue_unavailable`, a lost spawn recovered by the cron, and expiry after max attempts. |
| F3 | Functional | Lost or expired jobs are re-dispatched by a Modal schedule (the replacement for Celery beat). | Test: an expired lease is re-spawned. Deployed: a killed job recovers. |
| N1 | Non-functional | Locks: per-attempt and publication locks become MongoDB leases with fencing tokens. Deletion still waits for active writers. No soft-lock fallback. | Concurrency tests (two writers, deletion vs. active attempt, a holder crashing). The integration and recovery gates in CI. Independent review recorded. |
| N2 | Non-functional | Serial CPU execution is kept: at most one training/tuning container at a time. | Modal function concurrency set to 1; documented. |
| N3 | Non-functional | Secrets (Atlas URI, Claude key, project API keys) live in Modal or Vercel secret stores, never in the repo. Production mode requires project API keys. | Config review; the deployed API rejects requests without a key. |
| N4 | Non-functional | The local Docker, Kubernetes and CI paths are unchanged and keep passing. | All existing gates; `MLPP_JOB_DISPATCH=celery` stays the default. |

## Design (for option 1a)

1. **Dispatch.**
   - New setting `MLPP_JOB_DISPATCH=celery|modal` (default `celery`).
   - The `Publisher` interface gains a Modal implementation that calls
     `modal.Function.from_name(app, "train").spawn(experiment_id)` and the same for
     tuning.
   - Admission, `mark_dispatched` and the 503 path are unchanged.
   - Redis becomes optional when dispatch is `modal`: readiness skips it and the Redis
     URL check is relaxed.
2. **Modal app.** New `deploy/modal/app.py`:
   - an image with `--extra training`;
   - one Volume mounted at `/data` (`MLPP_DATASET_ROOT=/data/datasets`,
     `MLPP_ARTIFACT_ROOT=/data/artifacts`);
   - a `@modal.asgi_app` serving `create_app()`;
   - `train`/`tune` functions calling the existing `execution.run`/`tuning_execution`
     with a 660 s timeout and `max_containers=1`;
   - a `recover` schedule every 60 s calling the existing recovery query;
   - secrets from a Modal Secret.

   Volume writes are committed before a job reports completion; readers reload before
   reading.
3. **Locks.** `storage_control.py` swaps `FileLock` for a MongoDB lock collection.
   Each lock holds an owner token, a lease with heartbeat, a unique key per
   attempt/publication, and is released on exit. Deletion acquires them as today.
   Behind a `MLPP_LOCK_BACKEND=file|mongo` setting (default `file`).
4. **Atomic file publication on the Volume.** Same-container `os.link`/`os.replace`
   keep working. Cross-container visibility comes from Volume commit/reload at the
   points above.
5. **Vercel.**
   - `vercel.json` builds `frontend/dashboard` as a static site and rewrites `/api/*`
     and `/dashboard/config.json` to the Modal URL.
   - The Astro `base` and output directory get a Vercel build target, while the
     packaged FastAPI build stays for local use.
   - Grafana embedding is turned off on this target.
6. **Atlas.** A free cluster (it is a replica set, so transactions work), with the URI
   in secrets. Indexes are created by a one-off Modal function rather than on every
   cold start.
7. **Docs.** `docs/guides/public-deployment.md` gives the exact commands: Atlas setup,
   `modal secret create`, `modal deploy`, `vercel deploy`, a smoke test and rollback.

## Acceptance and verification

- Fast gates plus the new unit tests: the Modal publisher uses a fake `spawn`, and the
  lock backend is tested against MongoDB.
- Because of the lock and dispatch changes, the ordinary integration and isolated
  recovery gates must run. That needs Docker or CI, which this machine lacks, so they
  run in CI.
- Deployed smoke test run against the real URLs once the owner's accounts exist.
  Measure and record cold-start time and one training run's cost.
- Independent review of the lock backend and dispatcher before the first public
  deploy.

## Risks and rollback

- **Modal Volume consistency across containers.** Explicit commit and reload; a test
  writes on one container and reads on another.
- **Cold starts make the first request slow.** Measure; optionally keep one warm
  container (costs credits).
- **Costs.** Concurrency 1 plus the per-turn caps; the owner sets a Modal spending
  limit.
- **Public exposure.** Project API keys are required; uploads stay opt-in per project.
- **Rollback.** Remove the Vercel deployment and stop the Modal app. Atlas data
  remains. Local and CI paths are unaffected because defaults stay `celery`/`file`.

Out of scope: Grafana Cloud, custom domains, multi-region, GPU training, and removing
the packaged FastAPI dashboard.

## Human review and approval

Pending.

## Implementation outcome

Fill this section after implementation.
