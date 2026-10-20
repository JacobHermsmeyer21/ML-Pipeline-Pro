# Laptop Qwen latency diagnostic

The [October 18 cost investigation](../evidence/2026-10-18-qwen-cost-investigation/README.md)
attributes the saved prompt's tokens and explains why CPU saturation alone does
not establish contention. Its [follow-up experiment plan](../plans/2026-10-18-qwen-cpu-prompt-cost-plan.md)
now has Jacob's approval for resource profiling and request-local thread trials;
the [October 19 run](../evidence/2026-10-19-laptop-cpu-trials/README.md) completes
twelve valid uncached first steps but retains no faster thread setting. Application
defaults remain unchanged, and complete CPU attribution remains outstanding.

This first-step diagnostic predates the implemented
[five-minute laptop profile](laptop-five-minute.md). Later standalone ten/seven
gates pass, and two unbounded direct-AI workflows complete with application probes
removed; the bounded deployed walkthrough still fails. Those later results do
not establish a resource cause or replace this diagnostic's workload/provenance.

This implements Jacob's [approved bounded plan](../plans/2026-10-18-laptop-qwen-diagnostic-plan.md).
It diagnoses eventual first-step response on the Acer Ryzen 3 3350U laptop. A
successful result does not pass the original ten dialogue/seven snippet cases or
establish interactive demo readiness. Application timeouts remain unchanged.

Use the installed pinned Ollama 0.40.2 server, profile and local tokenizer from
[local setup](local-model-setup.md). Do not pull another model or run concurrent
inference. Start the existing server with `.tools/test-prerequisites/start-local-model.ps1`
if needed. Capture actual machine metadata immediately before running, from a
PowerShell session allowed to read CIM:

```powershell
New-Item -ItemType Directory -Force artifacts/laptop-qwen-diagnostic | Out-Null
$diagnosticCpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$diagnosticSystem = Get-CimInstance Win32_ComputerSystem
@{
    cpu = $diagnosticCpu.Name
    cores = $diagnosticCpu.NumberOfCores
    logical_processors = $diagnosticCpu.NumberOfLogicalProcessors
    manufacturer = $diagnosticSystem.Manufacturer
    model = $diagnosticSystem.Model
    physical_memory_bytes = $diagnosticSystem.TotalPhysicalMemory
    gpu = @(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name)
    power_plan = (powercfg /getactivescheme | Out-String).Trim()
} | ConvertTo-Json | Set-Content -Encoding UTF8 artifacts/laptop-qwen-diagnostic/machine.json

uv sync --locked --extra training
uv run --locked --extra training python -m evaluations.laptop_qwen_diagnostic `
    --run-laptop-diagnostic `
    --machine-info artifacts/laptop-qwen-diagnostic/machine.json `
    --output artifacts/laptop-qwen-diagnostic/run-01
```

The output directory must be new. Machine identity comes from the supplied local
CIM snapshot; this is an operator prerequisite, not hardware attestation. The
script stops on another CPU/manufacturer or an incompatible runtime/profile.
Preflight checks public model metadata and checksum-pinned tokenizer admission.
The original `read_guidance` fixture goes through the real host's first model
boundary using an in-memory store, then the SDK's mock transport captures exact
request bytes. Synthetic capture replies are never measured evidence.

One explicit warmup keeps context 8192 resident, with a separate 120-second cap.
One measured `/api/chat` request uses the captured bytes, output cap 1024 and a
480-second wall deadline. There are no retries or tool executions. Validation
replays the saved response through the strict adapter in memory and requires
`get_experiment` with exactly `experiment_id=exp-low`, plus matching token counts.
The full response is never repaired or parsed by extracting a JSON substring.

Inspect `result.json`, `request.json`, `warmup.json` and `response.json` when
present. Timings convert runtime nanoseconds to seconds; input/output token
counts remain separate. Windows API sampling targets five-second intervals;
saved monotonic timestamps expose actual delays. Samples record available physical
memory, system commit availability and cumulative CPU times. Commit availability
does not measure disk paging activity. CPU busy fraction over an interval is
`1 - delta(idle) / (delta(kernel) + delta(user))`; kernel time includes idle.
Residency reports `size_vram`, context and artifact identity. Existing prefix-cache
state is not cleared or assumed cold. No headers, credentials or environments are
archived. Review safe evidence before copying it into tracked documentation.

Timeout closes the response/client but may leave the server computing. Inspect
the local runner log and CPU activity for an idle/cancelled task before any later
request; `/api/ps` residency alone does not prove that inference stopped. Do not
automatically retry. Preserve timeout evidence and report unknown activity as a
verification gap. Changes to model/runtime, prompts, application deadlines or demo
arrangement require their own reviewed scope.

## Resource profiling and thread trials

The approved CPU experiment keeps the same first-step workload and the required
demo services running. First inspect `docker compose ls` and the runner log for
active work. Do not start another inference during the experiment. No duplicate
stack was found in the October 18 preflight; its service-stop candidate is omitted.
Capture fresh machine metadata using the PowerShell example above, then run:

```powershell
uv run --locked --extra training python -m evaluations.laptop_cpu_trials `
    --run-laptop-thread-trials `
    --machine-info artifacts/laptop-qwen-diagnostic/machine.json `
    --output artifacts/laptop-cpu-trials/run-01
```

Use a new output directory. The Windows observer runs in its own hidden process,
targets two-second samples and saves actual gaps, sampling duration, process
CPU/working sets, system CPU, AC status, memory/paging/disk counters and clocks.
Access failures remain explicit. Raw Windows performance counters, status/type
fields and timestamps are saved alongside Windows-formatted rates. Process CPU fractions use
the actual elapsed interval and all logical processors; PID reuse and missing
CPU access are excluded from attribution. The observer's own CPU is included.
Changing between AC and battery during the run makes the comparison ineligible.

Each 2/3/4-thread screen has a fresh automatic-thread baseline. Each request
unloads/verifies absence, warms the pinned model separately and verifies effective
inference threads and unchanged batch size/context. Both response and runner log
must establish zero cached tokens. Original strict read semantics are checked
using the existing adapter. At most one screen candidate receives three new
baseline/candidate pairs. Retention requires at least 20% lower median wall time
with no semantic failures; screening alone establishes no performance claim.

The run reserves 660 seconds before each trial, caps inference at 480 seconds,
warmup at 120 seconds, measured requests at 16 and total lifetime at 60 minutes.
The normal path uses 12 requests. Errors/timeouts stop without retry. Inspect
residual runner activity before another request after failure. Successful cleanup
unloads the diagnostic model and stops the owned observer; services and application
settings remain unchanged. Independent review is unavailable for this session;
deterministic tests and self-review are recorded separately from live evidence.
