# Diagnose Qwen latency on the presentation laptop

- Status: awaiting human review; implementation pending
- Date: 2026-10-18
- Source baseline: `cb67bb8` / `person-a/conversation-foundation`
- Request: recommend laptop inference improvements; try an eight-minute diagnostic to determine whether Qwen eventually responds.
- Human reviewer/approval: pending review of this bounded diagnostic design; the suggestion of a longer run does not approve application timeout/default changes.
- Independent review: no reviewer yet; seek separate review of wall-clock cancellation and request/token bounds before calling the harness reviewed.

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

Pending. Review covers this one-request diagnostic and its harness only. It does
not approve higher application deadlines, a new model/runtime, prompt-contract
changes or replacing the approved one-machine demo. Implementation starts after
explicit review; source inspection and this reviewable plan are already complete.

## Implementation outcome

Not implemented or executed. The current workstation cannot supply a laptop
measurement. No new application setting, model gate, test assertion or production
behavior changes are part of this plan record.
