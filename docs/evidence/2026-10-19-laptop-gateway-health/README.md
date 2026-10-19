# Laptop gateway health implementation and failed live acceptance

Jacob approved the [health plan](../../plans/2026-10-19-laptop-deployment-health-plan.md)
on October 19: "i approve, go for it". The local gateway liveness change is
implemented and pushed as `bf07213`. Required implementation checks pass, but the
**complete deployed demo fails again**, on its first AI inspection. Even the new
local nginx health response stalls; Kubernetes orders a liveness restart before
the AI reply deadline. This run does not justify increasing that deadline.

See [derived results](results.json), [unaltered execution payloads](raw.zip),
[payload hashes and byte counts](manifest.json), and [verification](verification.json).
Explanations below are separate from raw reports. No failed output is repaired,
retried or executed. Earlier [five-minute failures](../2026-10-19-laptop-five-minute/README.md)
and [accepted standalone ten/seven gates](../2026-10-19-laptop-awake-gates/README.md)
remain distinct, unchanged evidence.

## Provenance and implementation

The live run uses clean `bf07213ed2564cfc9c97efb35504c22f2d9cf9c7` on the Acer
Aspire A515-46 / Ryzen 3 3350U laptop, Python 3.11.17, Ollama 0.40.2 and installed
`mlpp-qwen2.5:7b-instruct-q4_K_M-json-tools-v1`, digest
`abadc4bf8517d77dcc8db312ca98cd7cb43488243048c41f1b5746e031427779`.
The actual runtime logs report four inference threads and context 8192. No model,
prompt, thread, token/call limit, resource allocation or probe threshold changes.
Budgets remain model 240 / shared turn 270 / complete client reply 300 / gateway
read 310 seconds. Default deployments retain their existing settings.

Only the opt-in laptop renderer adds exact `/gateway-live` returning local 200 and
points Kubernetes gateway liveness there. Readiness/startup still check upstream
availability. Rendering assertions compare every unrelated probe, resource and
replica setting with canonical definitions. The real nginx check establishes
NXDOMAIN and then a resolvable but refused TCP upstream; local liveness succeeds
while upstream health/readiness and `/gateway-live/` return correlated 503.

The named kind cluster `mlpp-laptop-five-minute`, namespace `mlpp-demo`, reuses its
saved data. Image `ml-pipeline-pro:health-dac4ee6` is built from the checked worktree
after approval; installed module hashes match the later implementation commit.
Host Docker manifest-list/load identity is
`sha256:050a5f0165b6e5293eb0bc13aeafa84bfd8b75024c570f6d96796a58bc47e460`;
active API pods report CRI image identity
`docker.io/library/import-2026-10-19@sha256:0716acbc39214a684aadc023640e34e088b8387494ca933ef85a98faab1d49d2`.
The authoritative `validation/active-installation.json` checks imported site-packages
and effective settings in all four running API pods, plus actual nginx/probes.
Copied `/app/src` bytes alone are not the installation proof.

## Verification results

| Check | Result |
| --- | --- |
| Locked sync, Ruff lint/format, dependency compatibility | Pass; 204 formatted files, 109 compatible packages |
| Full fast suite | 647 passed, 73 integration deselected; 81% rounded coverage; pytest 151.00 s |
| Focused renderer/timing checks | 18 passed |
| Real nginx negative routing check | Pass; final command 20.844 s, no inference |
| Package build | Pass; workspace-cache warning retained; archive inspection finds no `.uv-cache` entries |
| Ordinary real-service integration | 63 passed, no selected skips; pytest 87.58 s; both required flags |
| Actual rollout, backend and direct two-pod replay | Pass; saved records/artifact hashes/sizes/submission identity preserved |
| Named-node stop/start | Pass, 112.531 s; same saved records/artifacts/replay identity |
| Implementation CI | All five jobs pass in [run 39329050544](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/39329050544) |
| Complete actual-ID AI walkthrough | **Fail**, first AI request disconnects after 144.094 s |
| Fresh health-cohort ten/seven model gates | **Unrun** after first generation failure, as planned; earlier standalone passes remain valid only for their retained cohort |
| Isolated recovery | No new execution; prior complete ten-case result retained because ownership/queue/recovery code is unchanged |

Setup incidents are retained, not relabeled passes: the first focused invocation
lacks its output parent (14 passes/four setup errors, tool output only); the first
nginx attempt fails at Docker port discovery on an internal bridge. A separate
bridge allows the original assertions to execute; no success assertion is relaxed.
The initial format gate finds prior displayed draft examples; only that Markdown
presentation is Ruff-formatted, with all five ASTs checked against immutable raw
strings. Original reports/archive/human decision remain untouched. The initial
post-rollout collector tries a completed historical pod after rollout and data
preservation already succeed; separate active-installation verification passes.
The corrected focused run retains a pytest cache-permission warning; the full fast
run uses a fresh cache and passes. Original command exits/logs remain in raw.zip.

## Live failure timeline

One explicit empty-prompt warmup precedes the original walkthrough, invoked with
`--timing-profile laptop-five-minute --confirm-demo-proposal`. Backend classification,
three-trial Bayesian tuning, version creation and submission replay pass. There is
one AI request and zero automatic retries. No generated Python is executed.

| UTC, October 19 | Observed boundary |
| --- | --- |
| 21:39:46.260 | First inspection starts; saved original deadline 21:44:16.260 |
| 21:41:12 through 21:41:40 | Kubernetes records three timeouts for local `/gateway-live` liveness |
| 21:41:45 | Kubernetes orders gateway restart explicitly for failed liveness |
| 21:41:49.728 | Serving model API logs shutdown; API probes also fail during the stall |
| 21:42:10.369 | Port-forward loses its pod connection during gateway shutdown |
| 21:42:10.430 | Client command ends after `RemoteProtocolError`; AI request elapsed 144.094 s |
| 21:42:28 | Old gateway container finishes, exit 0 / Completed |
| 21:42:33 | Replacement gateway starts; API finishes saving the original turn at 21:42:33.023 |
| 21:45:49.749 | Separate later read observes runner idle and gateway restart count four, versus initial three |

Server `complete_turn` elapsed is **167.506 s**, within the original 270 seconds.
Runtime task totals are 125.648 and 22.661 seconds; those are runtime measurements,
not end-to-end latency. The saved response honestly reports a `get_experiment`
`tool_transport_error`, with no facts, proposal, snippet or submission. Thus neither
successful delivery nor semantic inspection acceptance passes. No deadline-expiry
or timely cancellation is demonstrated. History is recovered using pure MongoDB
reads and a GET; no chat replay or confirmation POST is sent after failure.

Initial/final pod snapshots both report the old gateway container and restart count
three, despite newer Killing events. Retain this lag rather than infer no restart.
Later pod state confirms restart count four, the old container's finish time and
the replacement start. Exit 0 / Completed is not OOM evidence. Similarly, original
`runner_idle_after=false` reflects a runtime slice read before final log collection.
It is preserved alongside the separately timestamped later idle observation.

The command takes 165.843 seconds including backend setup; outer rehearsal capture
takes 232.985 seconds including warmup and collection. These windows differ from
the failed request's 144.094 seconds. AC reads are connected/100% before and after;
all 13 host samples show AC connected. The temporary Windows system-required request
runs 21:29:34.773–21:48:17.183 and is then cleared without changing power policy.
The System-event query returns no matching records for that window, retaining its
No-events error; this does not independently prove complete power-log coverage.

## Resource evidence and limits

Thirteen host samples reach a minimum available physical memory of **557.81 MiB**
at 21:41:30.535. Page input is about 14,840 pages/s at 21:41:40.699, but its higher
21,098/s peak at 21:39:41.989 precedes the AI request. Page input can include
file-backed demand reads; these counters do not establish swap thrashing or cause.
All reported extrema use successful counter status codes.

The last successful node read begins at 21:42:08.073 and records CPU PSI
`some avg10=98.74`, memory PSI `some avg10=0.41/full avg10=0.00`, and
MemAvailable 6,655,816 KiB. PSI measures scheduling pressure, not application CPU
utilization. Gateway cgroup `nr_throttled`/`throttled_usec` remain zero in all three
successful samples; gateway quota exhaustion is not established.

Measurements lose the critical interval: maximum host gap 34.588 seconds, node gap
79.125 seconds, and one node frame takes 76.609 seconds. Subprocess waits return
after their nominal bounds under load; DNS durations include Kubernetes exec and
control-plane overhead. Cgroup mappings cover initial container IDs only.
The fixed host PID selection misses actual `llama-server` and cannot access vmmem
CPU/working-set counters. A later process snapshot finds the worker using about
4.83 GiB and vmmem about 5.02 GiB; that is not an inference-window CPU measurement.
Observer validation during image build establishes functionality, not an idle
baseline. Observers stop cleanly; no force-stop or extra inference is needed.

The evidence establishes broad scheduling/health stalls and liveness-triggered
shutdown, while the resource cause remains uncertain. It does not prove OOM,
specific memory exhaustion, model semantic failure, gateway quota exhaustion or a
need for longer reply windows. The next [reviewable diagnostic plan](../../plans/2026-10-19-laptop-resource-diagnosis-plan.md)
addresses missing worker/VM attribution with fixed application/model settings.

## Acceptance and review

F1/F2 implementation verification passes. **N1 and N3 fail**: a gateway liveness
restart still interrupts the first AI reply and the full workflow does not finish.
N2 produces retained measurements with explicit access/gap limitations; it does
not establish resource attribution. Fresh ten/seven reruns stop before execution
under the approved first-generation-failure rule. The earlier live under-load
deadline-expiry requirement and complete laptop course reproduction remain open.

The separate OpenAI `timing_review` agent reviews renderer/probe scope, real-nginx
preconditions, failure chronology and resource arithmetic read-only. It finds no
concrete implementation defect and confirms the attribution limits above. It runs
no services/inference; different-vendor review is unavailable. This is same-vendor
review, not human acceptance of this failed deployed output.
Its final text review also distinguishes the Docker load and pod CRI identities;
the next plan now covers baseline/workload/post-run capture within one total cap
and sets a finite post-run idle-polling deadline. Archive verification is separate
from this read-only review.

raw.zip contains allowlisted logs, JSON/JUnit reports, effective nginx, executed
observer/orchestration source and relevant committed source. The manifest records
exact bytes and hashes; verification checks ZIP CRCs and every payload hash. It
excludes kubeconfig, credentials, model weights, installers, environment dumps,
test caches and generated build artifacts. The kind cluster/PVCs remain; the old
Compose project stays stopped with volumes preserved. Resource settings, power
policy and API probe thresholds remain unchanged.
