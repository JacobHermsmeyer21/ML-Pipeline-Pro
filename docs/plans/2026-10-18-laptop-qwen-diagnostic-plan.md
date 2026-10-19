# Diagnose Qwen latency on the presentation laptop

- Status: approved; implementation and laptop diagnostic in progress
- Date: 2026-10-18
- Source baseline: `cb67bb8` / `person-a/conversation-foundation`
- Request: recommend laptop inference improvements; try an eight-minute diagnostic to determine whether Qwen eventually responds.
- Human reviewer/approval: Jacob, October 18, 2026: "Look at diagnositc plan, I approve it, start running tests on this laptop". Approval covers the bounded diagnostic and harness below; application timeout/default changes remain excluded.
- Independent review: a separate same-vendor Codex agent reviewed wall-clock cancellation, request/token/size bounds, tool isolation, strict validation and failure reporting on October 18. Four findings were corrected and re-reviewed; see the implementation outcome. External-vendor review unavailable.

## Proposed behavior and purpose

Run one representative pinned-Qwen inspection request directly against the
installed laptop Ollama server with a **480-second wall-clock budget**. Save the
answer, its semantic validity, exact request identity and separated loading,
prompt-processing and generation timings. Determine whether the existing failure
is slow successful generation, invalid output, memory pressure, or a client/API
timeout issue before changing the app or selecting another model.

## Clarification and critique

The audit session is on the RX 9070 workstation, not the CPU presentation laptop.
Actual laptop acceptance requires running the harness there. No remote laptop
access is established. Jacob has not chosen whether a workstation connection is
acceptable for the eventual demo; that is a separate arrangement to review.

The retained warmed laptop request spends 113.524 seconds on 1,147 prompt tokens
and 19.545 seconds generating 51 tokens. Slow inference is confirmed; the late
140.929-second API timeout mechanism is unresolved. Eight minutes can establish
eventual completion for a request, not interactive demo readiness or correctness.
App settings currently allow at most 60 seconds per model call / 120 per turn;
changing an environment variable to 480 is not a supported diagnostic shortcut.

Do not train/fine-tune Qwen for this deadline. It is already pretrained and uses
the evaluated 7B Q4_K_M profile. The earlier 3B alternative failed semantics.
Start with measurements, then compare a single proposed inference change at a
time. Streaming may improve visibility but does not establish faster completion.

## Requirements

| ID | Type | Requirement | Evidence |
| --- | --- | --- | --- |
| F1 | Functional | A representative original guided inspection request returns a complete, valid step or an explicit failure. | Original `read_guidance` fixture/input and expected `get_experiment` / `exp-low` read; no real mutation or code execution |
| F2 | Functional | Separate eventual response from semantic correctness and production acceptance. | Exact response, strict schema/tool-argument validation and independent result fields; no output repair |
| N1 | Resources | One measured request, at most 480 seconds total wall time, context 8192 and output cap 1024. | Monotonic duration, token admission, request hash, timeout/final status; no automatic retries |
| N2 | Reliability | Application limits, original gates, permissions, persistence and model support remain unchanged. | Diff and deterministic checks; diagnostic does not dispatch tools or write domain records |
| N3 | Provenance | Establish actual machine/runtime/model, loaded processor, context, resource use and cache conditions. | Public metadata, pinned digest/tokenizer, timing fields, bounded CPU/RAM observations; no environment/credential dumps |

## Constraints and scope

Reuse the explicit pinned 7B tag, runtime/template/tokenizer checks and existing
LangChain SDK request shape. No model pull, runtime upgrade, trained weights,
cloud endpoint, hidden cache priming, action submission or production setting
changes. Existing 20/60-second application limits and original ten/seven gates
remain acceptance criteria until a separately approved design changes them.
Stop rather than using another machine/model if laptop identity cannot be verified.

## Design

Add an opt-in diagnostic script and short guide after review. Capture the exact
first SDK `/api/chat` payload for the original `read_guidance` fixture through the
existing adapter/evaluation boundary without sending an inference. Reuse the
exact current guided instructions/schema and verified token admission. Submit
that safe captured request once via a diagnostic HTTP client to the installed
loopback runtime, with redirects/environment proxies disabled and no retries.
Validate the returned first step against the original expected scoped read; do
not execute it. This isolates inference and does not claim a complete chat turn.

Warm the installed artifact explicitly with context 8192 before the measured
request, recording warmup separately. Keep it resident for the diagnostic using
the existing supported keep-alive mechanism. Warmup remains capped at 120 seconds;
a failure stops the run. Bound the inference with a 480-second wall deadline in
addition to socket timeouts; save failure evidence and close the client on expiry.
Cancellation stops client waiting; confirm runner activity separately before
starting another request, since client cancellation alone may not stop inference.

Record total/load/prompt/evaluation durations and counts, output/schema validity,
CPU/RAM observations, model residency and power configuration when accessible.
Retain safe raw output under `artifacts/laptop-qwen-diagnostic/` and archive the
needed evidence after redaction. Do not log headers, credentials or full process
environments. Emit a clear diagnostic result, not an application-gate pass.

## Acceptance and verification

Before a real request, deterministic transport checks must prove one inference
request, no retry, no tools executed, exact captured payload, correct duration
units, bounded output, schema rejection and timeout handling. Run all repository
fast gates for the script change and inspect the actual laptop request/result.
No service/ownership behavior changes; rerun affected integration if the eventual
implementation touches those paths. Disclose unavailable independent review.

The baseline is the original fixture on the actual CPU laptop, warmed model,
one request/no concurrent inference, context 8192/output 1024, 480-second wall
budget. Completing within 480 seconds with the correct read establishes only
diagnostic eventual response. Timeout, malformed output or wrong arguments fails
that result. Successful full acceptance still requires original ten/seven gates
and an actual-ID tutorial on the final demo arrangement.

After baseline review, prioritize reducing unnecessary concurrent workloads and
checking memory/paging, then inspect prompt size. Compare any prompt/context,
threading, runtime or alternate-model experiment under a follow-up reviewed scope;
do not silently reduce context/output or remove required evidence to claim speed.
Current official documentation describes [timing fields](https://docs.ollama.com/api/chat),
[residency and parallel-memory controls](https://docs.ollama.com/faq), and
[context memory](https://docs.ollama.com/context-length). Confirm compatibility
with the pinned 0.40.2 runtime rather than assuming all current features apply.

## Risks and rollback

The laptop may remain too slow for an interactive demonstration even with correct
output. A cached request can flatter timing, resource sampling can be unavailable,
and a completed first step does not prove the follow-up reply or snippets. Record
these conditions explicitly. The diagnostic has no persistent/domain effect;
stop it and use the unchanged application/profile if rejected. Do not delete
weights, stored records or artifacts. A workstation-assisted demo requires its
own agreed arrangement and end-to-end rehearsal.

## Human review and approval

Jacob approved on October 18, 2026 in the request quoted above. Review covers this
one-request diagnostic and its harness only. It does
not approve higher application deadlines, a new model/runtime, prompt-contract
changes or replacing the approved one-machine demo. Implementation starts after
explicit review; source inspection and this reviewable plan are already complete.

## Implementation outcome

The [diagnostic harness](../../evaluations/laptop_qwen_diagnostic.py) and
[operator guide](../guides/laptop-qwen-diagnostic.md) are implemented on the actual
Acer Aspire A515-46 / Ryzen 3 3350U presentation laptop. The runtime reports
Ollama 0.40.2; model residency was empty before testing. Actual CIM metadata,
including Vega 6, 19,261,304,832 bytes physical RAM and the Balanced power plan,
is saved locally under `artifacts/laptop-qwen-diagnostic/machine.json`.

Thirteen new deterministic checks pass: original host-fixture/SDK capture,
strict read/argument/envelope/token validation, response-body and wall bounds,
no retry, nanosecond conversion, complete-run request counts and failure stops,
and rejection of a different machine before transport. These checks exercise
diagnostic safety/acceptance boundaries; existing assertions and original model
gates are unchanged. Locked sync passes (114 resolved / 109 installed packages),
Ruff lint and formatting pass (182 files), and all **611 fast cases pass**, with
73 integration/recovery cases deselected, no selected skips or warnings, 80%
rounded host coverage and 221.18 seconds test time. Dependency compatibility
passes for 109 installed packages. Local links/anchors, the PowerShell guide
example and `git diff --check` pass. Raw logs/JUnit are under
`artifacts/laptop-qwen-diagnostic/`. No service/ownership implementation changed,
so ordinary/recovery integration was not selected for this diagnostic addition.
The single live request remains pending immediately after the harness commit.

Separate review: same-vendor Codex agent `/root/diagnostic_review`, October 18,
2026, read-only review of the script/tests against this plan. Submitted scope:
wall cancellation, request/token/size bounds, exact SDK bytes, retry/tool
isolation, semantic validation, provenance and failure paths. Findings: bound
metadata reads; check resident name/digest/context; prevent post-response
metadata errors from retaining a passing status; test the complete orchestrator's
one-request and setup-failure behavior. All four were corrected and re-reviewed
with no remaining blocker. Machine fields are allowlisted and the CIM snapshot
is an operator prerequisite rather than hardware attestation. No external-vendor
review was available. The reviewer sent no live inference.

No application setting, dependency, model gate, persistent record or production
behavior changes are included. CPU busy observations use bounded Windows API
samples; physical/commit availability does not establish actual disk paging.
