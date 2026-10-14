# Laptop test prerequisite installation

October 14, 2026, at source `f13d5c3`: Jacob authorized installing Docker and
missing prerequisites for the requested inspection-fact verification. This is
machine setup and execution evidence; application contracts, evaluation cases,
assertions and budgets are unchanged.

Installed Docker Desktop 4.95.0.242831 (Docker CLI 29.8.2, Compose 5.6.0), Microsoft
WSL 3.0.3.0, and checksum-pinned standalone Ollama 0.40.2. Docker and WSL installer
signatures validated against their respective publishers. Windows Subsystem for
Linux and Virtual Machine Platform were enabled with `-NoRestart`. Windows reports
a required restart; no automatic restart was performed.

The approved Qwen 7B weights, custom template profile and immutable tokenizer are
installed and verified. Runtime weights stay repository-local, cloud is disabled,
and model/request concurrency remains one. Explicit empty-prompt warmup succeeds
without generating text. This laptop has a Ryzen 3 3350U, approximately 18 GiB RAM,
Vega 6 integrated graphics and firmware virtualization enabled. Ollama selects CPU
inference; prior RX 9070 results do not establish this laptop's speed.

The complete domain/monitoring/AI Compose configuration validates. Local container
startup and rebuilt-image walkthrough remain pending the Windows restart. MongoDB,
Redis, Prometheus and Grafana will come from the existing container stack. The
original failed demo/record is absent here; a fresh run cannot establish reproduction
against that record.

At the same application revision, the
[remote three-domain CI job](https://github.com/JacobHermsmeyer21/ML-Pipeline-Pro/actions/runs/38598353569)
passed all **63 real-service cases**, with zero failures, errors or skips, including
six conversation-service and three snippet cases. This is remote service-boundary
evidence, not local Docker or actual-model walkthrough evidence. See the retained
[raw checks](raw.zip) and [setup/source provenance](results.json).

The unchanged dialogue gate passes **2/10** on this laptop. Seven cases report
`chat_timeout`; the hostile-record case reports `model_unavailable`. Elapsed suite
time is 290.85 seconds. Two pytest cache permission warnings occurred separately
from the model failures; the snippet run uses a fresh artifact-local cache directory.
The source retains 20-second inference calls, a 600-second dialogue suite and a
120-second snippet suite. Historical prose describing both suites as 120 seconds
does not describe the current dialogue harness. No timeout override was supplied.
The snippet gate passes **0/7**, completing in 121.83 seconds. Its first two cases
report `chat_timeout`; remaining cases report `model_unavailable`. The retained
call ledger ends after four admitted calls; the harness rejects a further call
when less than a full inference deadline remains. Budget exhaustion is the likely
source of the later availability results, rather than evidence of an uninstalled
runtime. Both failures remain retained; no retry or output repair manufactured a
pass. The model was explicitly unloaded afterward to release laptop memory.

All five jobs in the implementation CI run finished successfully, including
Compose/recovery and Kubernetes. Those automated environments do not run the
opt-in installed-model gates and do not establish local CPU model acceptance.

After restarting Windows, start Docker Desktop and the pinned local server
(`.tools/test-prerequisites/start-local-model.ps1` in this workspace), then follow
[ordinary integration](../../guides/verification.md#ordinary-integration) and the
[walkthrough](../../guides/midterm-walkthrough.md). Helpers, installers and weights
stay ignored. The CPU model failures remain acceptance gaps; installing software
does not establish model performance. Separate boundary review remains unavailable.
