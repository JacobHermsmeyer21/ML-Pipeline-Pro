# Laptop prerequisites require a reboot and have separate model results

October 14, 2026: [setup evidence](../evidence/2026-10-14-prerequisite-setup/README.md)
records Jacob-authorized Docker Desktop/WSL installation and enabling both WSL and
Virtual Machine Platform with no automatic reboot. Both features report restart
required; WSL status still returns `WSL_E_WSL_OPTIONAL_COMPONENT_REQUIRED` before
that restart. Do not repeatedly reinstall them instead of activating the changes.

Docker is installed per user under `%LOCALAPPDATA%/Programs/DockerDesktop`.
Ollama 0.40.2, the pinned 7B weights/profile and tokenizer live under ignored
`.tools/local-model-setup/`; `.tools/test-prerequisites/start-local-model.ps1`
restarts the server with local weights/cloud disabled and concurrency one.
Repository-local uv and the locked Python environment are already installed.

This Acer laptop has Ryzen 3 3350U/Vega 6 and approximately 18 GiB RAM, rather than
the earlier RX 9070 system. Ollama selects CPU; unchanged model gates pass 2/10
dialogue and 0/7 snippets with timeouts/availability failures. Complete CI passes,
including 63 real-service tests without skips, but does not run these model gates.
No deadline/assertion changes or inferred GPU-equivalent performance are justified.
Recheck after reboot or a separately evaluated runtime/hardware change. The model
was unloaded after tests; explicit warmup is still needed before another gate.

Same-day [post-reboot validation](../evidence/2026-10-14-post-reboot-validation/README.md)
activates the hypervisor/WSL 2 backend; Docker starts successfully after initial
distribution provisioning. All 63 ordinary local integration cases pass without
skips. An old Windows pytest temp directory denies access in the initial run;
use a fresh `--basetemp` under workspace artifacts rather than changing tests or
broadly changing filesystem permissions. The complete AI walkthrough remains
unsuccessful; see [observed timeout overrun](cpu-inference-timeout-overrun.md).

October 19 follow-up: the reboot/installation boundary is resolved. Later
[five-minute standalone gates](../evidence/2026-10-19-laptop-awake-gates/README.md)
pass ten/seven on AC with human acceptance; these supersede the earlier partial
gate status for that profile only. The bounded deployed walkthrough still fails,
while two [unbounded direct-AI diagnostics](../evidence/2026-10-19-laptop-unbounded/README.md)
pass with application probes removed. Keep explicit warmup, AC/awake prerequisites
and machine/profile provenance; these results do not diagnose the earlier overrun.
