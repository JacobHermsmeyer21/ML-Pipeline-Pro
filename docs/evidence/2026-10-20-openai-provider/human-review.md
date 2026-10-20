# Hosted output samples for human review

Status: awaiting Jacob's usefulness review. These samples come directly from the
passing real-ID HTTP walkthrough; source evidence and limits are in [the record](README.md).
The isolated test stack was removed after validation. These retained IDs are
evidence references, not a current interactive demo. Generated code was not executed.

## Recorded fact and generated guidance

The following fact is from the worker-backed saved experiment:

```json
[
  {
    "record_id": "dbe82cf5-00da-4bf3-9008-a228ca7c7784",
    "field": "metrics.validation_f1",
    "value": 1.0
  }
]
```

The following explanation is model-generated:

> Verified fact: experiment dbe82cf5-00da-4bf3-9008-a228ca7c7784 succeeded, and its metrics.validation_f1 is available from the returned record. Next-step guidance: if you are choosing among candidate experiments on the same dataset, compare validation_f1 across them before selecting a winner; if this is the current best run, you can proceed to final evaluation on the held-out test split after selection. The record also shows validation_accuracy and best_epoch, but I am only surfacing the requested validation_f1 fact here.

## Validated generated Python draft

The host accepted this draft's restricted syntax/API shape. It still needs human
review of usefulness and intended settings before use. Its environment variables
are placeholders for the engineer's execution environment; no credentials are embedded.

```python
import os
import httpx
with httpx.Client(base_url=os.environ['MLPP_API_ORIGIN'], headers={'X-Project-ID':os.environ['MLPP_PROJECT_ID'],'X-API-Key':os.environ['MLPP_API_KEY']}, timeout=10, follow_redirects=False, trust_env=False) as client:
    response = client.get('/api/v1/experiments', params={'limit':50,'offset':0})
    response.raise_for_status()
    data = response.json()
```

## Generated monitoring interpretation

Input observations declared a synthetic 150ms seeded delay; these are not measured
inference latencies. The interpretation below is generated, and no fix ran.

```json
{
  "interpretation": "This complete 5-minute window shows availability with zero errors, but latency is above the 100 ms threshold (mean/max 150 ms). The seeded_count of 3 indicates a declared artificial latency injection, so the observed delay may be expected rather than evidence of stress or contention. Accuracy cannot be assessed because labeled_count is 0 and labeled_accuracy is null. Use these measurements as signals only; the underlying cause remains unknown.",
  "observation_ids": [
    "0a8a7f92-1e58-596e-bb2f-199636cf053b",
    "c32e0987-597c-5a68-a4de-d3b3d06e7d64",
    "1d5aabd0-1d75-54ae-8e5e-4d489cd7b2d3"
  ],
  "proposed_checks": [
    "inspect_seeded_delay",
    "profile_inference",
    "collect_labels"
  ]
}
```

Review whether the guidance, draft and diagnosis are clear and useful. Existing
local-model human approval does not approve these hosted samples.
