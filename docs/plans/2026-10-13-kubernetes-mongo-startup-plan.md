# Recover the classroom MongoDB process after early DNS startup

- Status: approved deployment/probe scope; diagnosed fix pending
- Date: 2026-10-13
- Baseline: `2945bd2`
- Human approval: Jacob's approved minimal deployment implementation request
- Independent review: separate boundary reviewer; different-vendor unavailable

## Problem and requirements

After resuming the explicitly named kind test node, MongoDB answers ping but
reports `InvalidReplicaSetConfig` and `isWritablePrimary=false`. Its saved config
still names `mongo:27017`; the headless Service publishes the actual pod address.
The MongoDB pod remains unready, while API dependency ping readiness passes and
POST datasets returns storage-unavailable 503. No successful write is claimed.

Implement a bounded startup probe using the existing replica-set initialization
and writable-primary check. It allows twelve five-second attempts; failure restarts
only the MongoDB process, retaining its PVC/config/data. Readiness keeps the same
writable check. This addresses startup when DNS is temporarily unavailable, rather
than rewriting a valid saved replica-set config or broadening application readiness.

## Scope and critique

This is a diagnosed correction within the approved local deployment/probe behavior,
not a new public API/default, replica-set topology or production availability claim.
An operator-only manual restart would leave the supported restart failure unresolved.
Do not force-reconfigure MongoDB, delete its PVC, add API retries or hide failed writes.
The timer is a local startup allowance, not a guaranteed recovery SLA.

## Verification and review

Inspect the live membership/error mechanism, review probe initialization/restart
boundaries independently, and exercise this only in the disposable named cluster.
Temporarily stop its CoreDNS during a MongoDB process restart, restore DNS, verify
the unhealthy process restarts into writable primary and existing saved records
survive. Retain pre/post counts, failure state, pod restart count and raw commands.
Run actual backend/local-AI/replica checks afterward. Re-exercise fresh deployment
CI. Validate manifest syntax, docs/whitespace and relevant existing fast gates.

## Human review scope and outcome

Within Jacob's already approved reliable classroom deployment and health-probe
implementation scope; no separate human review of this document is claimed.
Material changes beyond that direction require renewed review. Outcome pending.

Implementation: the retained DNS-outage test observes invalid membership, then one
automatic startup-probe restart. DNS is restored to its original two replicas;
MongoDB becomes writable with the same dataset IDs and config version 1, without
forced reconfiguration or deleting data. A first short outage recovered before
the probe fired and failed the restart assertion; it is retained separately.
The final test holds the fault through the configured allowance, preserving that
assertion. Separate same-vendor boundary review found no blocker; different-vendor
unavailable. Startup monitoring stops after success and is not general liveness.

The first remote deployment run timed out with one of two API pods available;
its artifact lacks the cause. Add bounded read-only pod/event/application-log
diagnostics before cleanup, preserving the original failure and all gates. This
does not assert that the local MongoDB mechanism caused that CI timeout. Fresh
deployment CI and the restored-cluster full demo remain pending.
