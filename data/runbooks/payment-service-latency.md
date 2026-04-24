---
id: payment-service-latency
title: Mitigate payment-service latency spike
service: payment-service
severity: P1
incident: INC-001
tags: [database, connection-pool, latency, rollback]
last_updated: 2026-04-23
owner: db-team
---

# Mitigate Payment-Service Latency Spike

Use this runbook when `payment-service` p99 latency exceeds the 5 s SLO threshold
and checkout failures are reported — as seen in INC-001.

## Context

Root cause of INC-001: a slow query introduced in **deploy v2.3.1** exhausted the
database connection pool, causing cascading latency across `payment-service` and
`order-service`.

## Prerequisites

- `kubectl` configured with `prod` cluster access
- Write access to the `payments` namespace
- Ability to trigger a deployment rollback via CI/CD or `kubectl`

## Diagnosis

1. **Confirm latency spike in monitoring**
   ```bash
   # Check p99 latency for the last 30 minutes
   kubectl exec -n payments deploy/payment-service -- \
     curl -s http://localhost:9090/metrics | grep http_request_duration
   ```

2. **Check pod error logs for connection-pool exhaustion**
   ```bash
   kubectl logs -n payments deploy/payment-service --tail=200 | grep -i "connection pool"
   ```

3. **Identify the current deployed version**
   ```bash
   kubectl get deploy payment-service -n payments \
     -o jsonpath='{.spec.template.spec.containers[0].image}'
   ```

## Mitigation

### Option A — Roll back to the last known-good version (preferred)

```bash
# Roll back to the previous deployment revision
kubectl rollout undo deployment/payment-service -n payments

# Confirm rollout completes
kubectl rollout status deployment/payment-service -n payments
```

### Option B — Emergency connection-pool increase (buys time while rollback is prepared)

Update the `DB_POOL_SIZE` env var in the deployment:

```bash
kubectl set env deployment/payment-service \
  DB_POOL_SIZE=50 \
  -n payments

kubectl rollout status deployment/payment-service -n payments
```

> **Note:** Option B is a temporary band-aid. Always follow up with Option A.

## Verification

1. **Latency returns below 500 ms p99**
   ```bash
   kubectl exec -n payments deploy/payment-service -- \
     curl -s http://localhost:9090/metrics | grep http_request_duration
   ```

2. **Checkout success rate recovers**
   ```bash
   kubectl logs -n payments deploy/payment-service --tail=50 | grep "checkout"
   ```

3. **Database connection pool no longer saturated**
   ```bash
   kubectl logs -n payments deploy/payment-service --tail=50 | grep -i pool
   ```

## Post-Incident

- Open a post-mortem in `data/postmortems/` within 24 hours.
- File a ticket to add a slow-query alert to the CI/CD pipeline.
- Increase DB connection-pool size permanently via infrastructure-as-code (not `kubectl set env`).

## Escalation

If latency does not recover within **15 minutes** after rollback:

1. Page `db-team` via PagerDuty.
2. Escalate to P0 if checkout failures exceed 10 % error rate.
3. Notify `#incidents` Slack channel with current status.
