# Dataset short-ID acceptance

October 20, 2026, implementation working tree based on `e7e6bb2`. Jacob directly
authorized implementation without another plan-approval step and explicitly
required agent understanding of d1/d2. See the
[authorization and scope](../../plans/2026-10-20-dataset-short-ids-plan.md).

Datasets now expose permanent project-scoped dN references through the same
registry as eN/cN. Existing canonical IDs, relationships, request fingerprints,
recipes and artifacts remain intact. Agent read targets resolve canonically;
saved mutation proposals and confirmation dispatch retain the exact d1 argument.

| Check | Result |
| --- | --- |
| Locked sync, Ruff lint/format, dependency compatibility | Pass; 121 compatible installed packages. |
| Full fast gate with coverage | 842 passed, 128 deselected, 79% reported total coverage. |
| Full ordinary integration, both flags | 116 passed, 854 deselected; no selected skips. Separate stack ports 18002/37018/16380. |
| Isolated serial recovery | 12 passed, 958 deselected; its own `mlpp-recovery-e841af6d5c4a` stack. |
| Dataset boundary cases within ordinary gate | Twelve simultaneous dataset publications, transaction conflict retry, migration preserving eN mappings, original-path deletion receipt replay/nonreuse and column replay after real parent deletion pass. |
| Agent/worker/browser acceptance | Three real guided Qwen 7B turns: inspect d1, inspect d2, propose training using d1. Canonical row-count facts, exact d1 proposal/hash/dispatch and repeated approval pass. One real worker run succeeds using the canonical dataset and its artifacts pass size/hash verification. Chrome cards/selectors/starter prompt/reload pass. |
| Local-model profile | Ollama 0.40.2, pinned 7B JSON-tools artifact, verified tokenizer; finite 120-second turn / 60-second model profile, no hosted calls. |
| Package build | Wheel and sdist build, dataset namespace included, actual cache/tool/secret exclusions inspected despite generic in-source uv-cache warning. |
| Independent review | Separate local Qwen 14B review; [findings, source-based resolutions and limits](review.md). |

The first live-model attempt failed safely with `model_unavailable` before a
tool read because the local runtime was stopped. A direct metadata probe confirmed
connection refusal. Restarting the installed pinned runtime with existing weights,
cloud disabled and one loaded model allowed the complete rerun to pass. The failed
and successful reports are retained; no product timeout or assertion was relaxed.

The first new test run exposed two harness setup errors (missing imported fixture
and omitted HTTP byte cap); both were corrected. A real deletion test initially
queried the wrong collection name; it now inspects the store's actual operations
collection and verifies the original request hash. Existing migration assertions
only gain an explicit dataset-namespace zero count. Other existing assertions and
all skip gates remain intact.

`manifest.json` records application source hashes and evidence archive hashes.
`raw.zip` retains fast/ordinary/recovery logs/XML, failed and successful live-model
reports, exact independent-review inputs/output/provenance and package-build log.
`datasets.png` shows the successful isolated browser view. Live demo rollout
results are recorded before the completion handoff. No broader
model-reliability, load/scaling, hosted-provider or course-acceptance claim is made.
