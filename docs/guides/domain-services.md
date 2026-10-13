# Separate domain services

Model-management and tuning run independently from the same image/repository.
They share MongoDB, Redis and artifacts; the serial worker continues to use both
repositories in one database session. Monitoring remains outstanding, so this
two-domain slice does not close C2 or C8.

## Run the domain topology

Use Docker Compose 2.24.4 or later from the repository root:

```powershell
docker compose -f compose.yaml -f compose.services.yaml up --build --wait --wait-timeout 300
if ($LASTEXITCODE -ne 0) { throw 'Domain stack failed to start.' }
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready
```

Gateway port 8000 routes `/api/v1/tuning-jobs` and child paths to `tuning-api`;
model/experiment/conversation paths go to `model-api`. Project, API-key and
submission-key headers pass through; valid correlations are preserved. Gateway
transport failures return normal JSON errors with HTTP 503/service_unavailable.
The proxy never retries mutations; domain HTTP errors pass through unchanged.
Model docs: `http://127.0.0.1:8000/docs`. Tuning docs:
`http://127.0.0.1:8000/tuning/docs`. Each describes only its owned operations.

Gateway readiness currently reflects the model API's MongoDB/Redis check, not
all-domain readiness or worker progress. Compose waits on both domain healthchecks
at startup. The gateway uses Docker DNS refresh for independent container
replacement; its DNS configuration is specific to Compose.

Use the same project-key map/database/artifact paths on both domains. Chat remains
opt-in and needs the verified local-model factory/counter. The separate host Qwen
API on 8001 can keep using gateway 8000 for tools. Images contain no model weights
or tokenizer. Stop with the same two `-f` options and `down`; volumes remain intact.
The base Compose file remains the compatibility/recovery stack. Switch back with
`docker compose up --build --wait --wait-timeout 300`; remove unused domain
containers explicitly afterward while preserving volumes.

## Host factories and verification

Use `ml_pipeline_pro.main:create_model_app` and
`ml_pipeline_pro.main:create_tuning_app`. Both retain health, access/errors and
correlations; tuning initializes no model client. `main:create_app` retains all
original operations for compatibility/recovery. Tuning still checks referenced
records through shared tracking; worker ownership writes are unchanged.

Run [ordinary integration](verification.md#ordinary-integration) with both flags
against the domain topology; queued HTTP cases exercise public routing. Run serial
recovery using its original base/override files and unchanged assertions.
Monitoring, Kubernetes and live AI acceptance remain separate outstanding gates.

The read-only `scripts/check_domain_routes.py` checks actual routed OpenAPI
ownership, domain 404 errors and correlation handling. Its `--tuning-unavailable`
mode checks the normal JSON 503 shape while only tuning is stopped. Restart tuning
after that exercise. The new `domain-compose-smoke` CI job checks this topology
and ordinary integration; remote outcomes must be checked separately.
