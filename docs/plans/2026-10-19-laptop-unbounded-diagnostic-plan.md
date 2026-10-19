# Measure laptop completion without AI wait cutoffs

- Status: approved; implementation and verification in progress
- Date: 2026-10-19
- Source baseline: `98b4908` on `person-a/conversation-foundation`
- Request: stop health checks interrupting work; measure one or two runs without a reply-time limit
- Human direction: Jacob says "yeah, lets not worry about the health checks, lets just let it work until its finished", then "lets do a run or two with no limit and see how long it takes, then go from there"
- Human design review: Jacob approved this written design on October 19, 2026: "go for it"
- Separate review: OpenAI `timing_review` read-only design review completed; different-vendor review unavailable

## Proposed behavior and purpose

Measure one complete original laptop walkthrough with no automatic AI model,
turn or client waiting cutoff and no application health-probe intervention. If
that first run finishes correctly, perform one second fresh run to show variation.
Record every elapsed time and semantic failure; use the observations to propose a
future finite demo budget. This is an explicitly opt-in diagnostic. It does not
replace the approved five-minute profile or pass its performance acceptance gate.

## Clarification and critique

The [retained failure](../evidence/2026-10-19-laptop-gateway-health/README.md)
establishes liveness-triggered gateway shutdown, not reply-window exhaustion.
Disabling only client waits is insufficient: Settings caps model/turn values at
300 seconds, the host installs asyncio timeouts and stores a turn deadline, and
MongoDB reconciliation rejects completion after that saved deadline. Those
ownership protections cannot silently be disabled on existing conversations.

The user's new instruction explicitly replaces the five-minute ceiling for these
one or two measurements. Do not substitute an undisclosed hour/day timeout and
call it unlimited. Preserve token, call, payload and schema constraints: removing
waiting limits does not authorize infinite tool loops or generated-code execution.
Stop on an actual transport/model/tool/semantic failure and retain it; waiting
longer cannot repair a failed request. The operator may explicitly stop a run.

Remove probe intervention only in the diagnostic application's rendered manifest.
Keep MongoDB/Redis and cluster control-plane checks unchanged. Kubernetes
[liveness/startup checks can restart containers, and readiness affects routing](https://kubernetes.io/docs/concepts/workloads/pods/probes/).
For gateway/model/tuning/monitoring, remove all three probe types in this temporary
profile and use explicit preflight HTTP checks before inference. Do not describe
the resulting Kubernetes Ready condition as evidence of dependency availability.
API health endpoints must continue returning truthful results when queried.

Avoid the gateway on long AI HTTP waits: nginx's
[proxy read timeout measures gaps between upstream reads](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_read_timeout),
and its documentation does not establish that zero disables that timeout. Forward
the two AI-serving pods directly for these measurements. Keep normal backend
calls through the existing gateway. This deliberately measures a different AI
delivery path; it cannot establish the normal gateway's unlimited reliability.

## Requirements

| ID | Type | Requirement | Evidence |
| --- | --- | --- | --- |
| F1 | Functional | Actually remove model/turn/client waiting cutoffs in the diagnostic path. | Effective None timeouts, saved explicit diagnostic deadline mode, beyond-300-second deterministic tests, direct AI request targets and timed live replies. |
| F2 | Functional | Preserve normal bounded behavior and previously saved deadlines. | Default/five-minute settings, replay/expiry/fencing tests, original scenario assertions and canonical deployment byte comparisons. |
| F3 | Functional | Health probes do not restart or withdraw diagnostic application pods during inference. | Effective four-deployment manifest; before/during/after events, container IDs and restart counts; real health failures remain visible in responses/logs. |
| N1 | Measurement | Retain complete execution provenance and observed completion times. | UTC/monotonic windows, pinned model/runtime/source/settings, AC/awake state, raw client/server/runtime/history evidence and explicit missing observations. |
| N2 | Safety/correctness | One active inference and at most two fresh walkthroughs, without output repair or executed generated Python. | Fresh IDs/output paths, explicit run count, unchanged model/call/token/schema/action assertions, observed idle between attempts. |

## Constraints and scope

Keep existing model, four inference threads, serial workers, two model API
replicas, domain separation, resource allocations and locked dependencies. Preserve
project/auth scoping, error/correlation schemas, action hashes/confirmation,
submission idempotency, training/tuning deadlines and artifact hashes/sizes.
No model/prompt/resource optimization, production unbounded mode or automatic
generation retry. Dependency connections, backend jobs, confirmed mutations and
small tool HTTP operations retain their existing failure bounds; the removed
limits apply to AI generation/complete-turn waiting, not every network operation.

## Design

Add an explicit `laptop-unbounded-diagnostic` execution profile and
`MLPP_CHAT_UNBOUNDED_DIAGNOSTIC` flag, default false and rejected in production.
Allow null model/turn timeouts only with that flag. Parse the documented literal
`none` for those two settings; reject zero, negative, infinity and NaN. Set both
LangChain/Ollama HTTP and host asyncio timers to None in this mode. Keep existing
default/five-minute finite validation and comparison unchanged. Document new
settings in `.env.example`, README and the laptop guide.
Require both timeouts to be null in diagnostic mode; reject mixed null/finite
configurations and null values without the explicit diagnostic flag.

Extend the private reservation with an explicit timeout-mode marker and nullable
deadline, permitted only for newly created diagnostic turns. Persist matching
markers/deadlines on both the active conversation parent and turn row, fenced by
the same owner token/active turn ID/revision. Finite records retain their original saved deadlines in every
profile, including replay and recovery. Reconciliation skips time expiry only for
an explicitly marked active diagnostic turn with a null deadline; malformed
unmarked/null owned turns and mismatched parent/child modes/deadlines must fail
closed. Normal and snippet admission/completion checks use the saved claim's mode,
never just the currently configured global flag. Completion still writes/fences the
parent and checks the same owner token, active turn ID, project and revision in
one transaction. Do not relax any action/training/tuning ownership or expiry.

Use a fresh diagnostic project and new conversations, preserving prior evidence
and records. After an owner crashes, retain saved public status `running`; record
`unknown` only as an external diagnostic outcome, not a new public TurnStatus.
Do not silently resume it or claim a completed result. A later attempt
uses fresh IDs only after confirmed runner idleness. No new automatic takeover
or cancellation API is included. Rollback must preserve readers capable of
understanding marked diagnostic rows; do not deploy older code over them blindly.

Extend the renderer for this explicit profile; only its four application
deployments omit startup/readiness/liveness probes. The normal laptop profile's
currently reviewed probes remain unchanged. Keep `/gateway-live` as a diagnostic
endpoint. Preflight verifies actual dependencies, routing and source/settings
after rollout, because missing probes cannot establish readiness.

The diagnostic walkthrough client forwards to one verified model API pod for chat
and one verified monitoring API pod for advice, with timeout=None on those AI
clients. Backend calls retain the existing gateway route. Add explicit diagnostic
AI-origin arguments; require both for this profile and record actual targets.
No inferred fallback or request retry. Original backend/history/fact/proposal/
confirmation/draft/replay/monitoring assertions still apply. Its output labels
timings as observations and never turns a reply above 300 seconds into a passed
five-minute acceptance result. Original ten/seven evaluation gates reject this
profile and keep their existing limits/assertions.

## Acceptance and verification

Before deployment, run locked sync, lint, format, all fast tests with coverage,
dependency compatibility and package build. Add meaningful tests for diagnostic
configuration gating, SDK/asyncio None propagation, preserved old deadlines,
nullable-deadline parent fencing, duplicate replay, malformed records and owner
loss. Test mismatched parent/child markers/deadlines in real MongoDB transactions.
Extend real MongoDB conversation cases for those transitions. Run all
ordinary integration with both required flags and isolated recovery serially with
its separate flag because persistence/ownership handling changes. Keep every
selected-case skip or missing service visible as a verification gap.

Obtain separate review of the nullable-deadline state changes before implementation
is called reviewed. Verify installed module hashes and effective settings in the
real pods. Record a manifest diff proving only the diagnostic profile changes
probes/AI waits; preserve data and artifacts during rollout. No inference until
AC/awake, actual HTTP preflight and runner-idle checks pass.

Run the original actual-ID walkthrough once in a fresh evidence directory, with
the existing explicit bounded demo-proposal confirmation. There is no automatic
AI reply/suite/process wall-time kill in this diagnostic. Record intermediate
progress while waiting. At a failure, stop the walkthrough and collect evidence;
do not continue or automatically retry. Only after a fully correct first run and
observed idle may a second fresh full run start. Record both cold/warm context
conditions; two observations are not a latency distribution or a proven upper bound.

Use lightweight sampling; do not require the pending resource-diagnosis harness
or treat unavailable counters as grounds to terminate useful inference. Clear only
owned temporary wake requests/collectors/forwards on completion or explicit user
stop, without killing the model as observer cleanup. Do not change power policy.
Save a running/completed/interrupted diagnostic status honestly. Normal gate
acceptance, full gateway reliability and real bounded-expiry evidence stay open.

## Risks and rollback

A deadlocked unbounded request has no automatic recovery deadline. Repeated
progress updates must not claim progress when only time is passing. Operator stop,
process crashes and machine sleep are retained as distinct incomplete outcomes.
Probe-free application pods can be unavailable despite Kubernetes Ready; explicit
preflight and actual response assertions provide evidence, not healthy-looking
status. Real process exits and node/OOM failures can still stop execution.

After the experiment, restore the normal laptop manifest and finite settings only
after outstanding inference completes or an explicit stop is recorded. Verify
original probes and 240/270/300-second waits, preserve records/PVCs/artifacts and
do not extend or rewrite saved finite deadlines. Existing diagnostic records keep
their explicit mode for truthful replay/history. Propose the next finite budget
from the measured results; no further budget or resource change is implied.

## Human review and approval

Jacob approved the written plan on October 19, 2026: "go for it", responding to
the published design and its explicit saved-turn-expiry/direct-AI-path scope.
Approval covers its diagnostic settings, parent/turn ownership handling,
probe-free application deployment, required checks, one complete measured run and
a second fresh run only after a correct first result and observed idleness.
Normal profiles, prior finite deadlines, action/job budgets and original semantic
assertions remain unchanged. The resource-only plan stays unapproved/deferred.

## Implementation outcome

The approved implementation is committed/pushed as `1152aa8`. Both measured
diagnostic workflows pass; normal finite gateway acceptance remains open.

The implementation adds gated nullable settings, matching saved parent/turn modes,
saved-claim-based admission and fenced completion, a separate rendered diagnostic
profile and explicit direct AI origins. Default/five-minute profile settings,
probes, canonical files and public schemas remain unchanged. Original semantic
assertions remain; diagnostic timings cannot pass finite-profile acceptance.
Locked sync/lint/format/dependencies and package build pass. All 661 fast cases
pass (83 integration deselected, 151.69 seconds, 80% rounded coverage); 203 focused
cases pass, followed by 14 diagnostic cases including actual None timer inspection.
All 73 ordinary integration cases pass against the rebuilt Kubernetes deployment
(95.90 seconds, both opt-in flags, no selected skips). All 10 isolated recovery
cases pass (370.64 seconds, separate opt-in, no selected skips). All five
implementation CI jobs pass. The [retained execution](../evidence/2026-10-19-laptop-unbounded/README.md)
uses clean `1152aa8`, matching installed module hashes and unchanged model/runtime.

The original complete walkthrough passes twice in 789.906 and 641.016 seconds.
First-run generated replies take 201.047/276.594/126.719/161.766 seconds; second-run
replies take 125.672/273.719/56.063/164.500 seconds. Exact proposal/draft replays
and confirmed bounded tuning pass. Saved marked-null turns complete, with no
container restarts. Each run ends idle before continuation/restoration. Initial
probe-free startup readiness fails with connection refused; later explicit HTTP
preflight passes before any inference. Both observations are retained separately.

The normal five-minute settings/probes are restored after idle, preserving records,
artifacts and replay. Owned forwards close and the temporary wake request releases.
New generated output quality awaits human review; Python is never executed.
The comparison replies exceed the former 270-second turn and stay below the
300-second client. Review the shared-turn budget before enlarging the client
ceiling. No new finite budget, routing/probe design or resource change is implemented
by this result. Full finite gateway acceptance, live expiry and resource attribution
remain open; two direct-AI/probe-free runs do not establish a latency upper bound.

Same-vendor implementation review by `timing_review` finds no concrete source
defect. Its two verification gaps lead to actual asyncio None-timer inspection
and real-Mongo parent-write interleavings for answers/proposals after a valid
snapshot; both now pass. The unit fixture only propagates the new private claim
mode; it does not substitute for transactional ownership evidence. No original
gate assertion is weakened.

The same reviewer also verifies the measurement journal is saved before warmup
and immediately after child exit, records interruptions/capture failures, hashes
executed helpers and defers cleanup while inference may remain active. An offline
simulated preflight refusal verifies retained failure status without model/network
calls. These capture checks do not establish a successful live measurement.

The separate OpenAI `timing_review` agent finds no blocker to plan publication.
Its two findings require matching parent/turn timeout modes and distinguish saved
public `running` from external uncertainty after a crash; both are incorporated
above, with saved-claim-based admission checks. This is same-vendor read-only
design review, not implementation/runtime verification or human design approval.
Different-vendor review is unavailable.
