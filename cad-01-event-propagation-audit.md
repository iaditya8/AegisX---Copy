# AegisX CAD-01 Event Propagation Audit Report
## Outbox and Event Dispatch Pipeline Trace

This report documents the event propagation auditing, tracing events from transactional outbox commits through Celery queues to consumer state mutations.

---

## 1. Event Propagation Pipeline Trace

For every core event, the lifecycle was verified against the database and broker:

```
[User Action] 
   ↓
[DB Transaction Commit (includes Outbox entry)]
   ↓
[Outbox table polling / Celery task enqueue]
   ↓
[Celery Worker thread execution]
   ↓
[Event Store table persistence]
   ↓
[Event Consumer listener updates]
   ↓
[Final State rendering in UI]
```

---

## 2. Walkthrough Event Traces

### 2.1 Finding Created
* **Action:** Scanning engine normalizes raw scan findings.
* **Outbox entry:** `finding.created` written in same transaction.
* **Worker task:** Normalized findings parsed and stored.
* **Consumer:** Security fabric evaluates confidence metrics.
* **Outcome:** Clean propagation, zero lost events.

### 2.2 Alert Created
* **Action:** Escalation logic matches finding parameters.
* **Outbox entry:** `alert.created` logged.
* **Worker task:** Evaluates correlation matches.
* **Consumer:** Correlation engine aggregates matches into a cluster.
* **Outcome:** Succeeded.

### 2.3 Incident Automated
* **Action:** Rule matches trigger auto-incident rule.
* **Outbox entry:** `incident.created` logged.
* **Worker task:** Creates and links incident in database.
* **Outcome:** Succeeded.

---

## 3. Propagation Integrity Verdict

The event pipeline was verified:
* **No Event Loss:** Transaction commits enforce that outbox entries are committed atomically with parent resources.
* **No Duplicate Events:** Celery tasks use task IDs and Redis message deduplication locks.
* **No Stuck Events:** Active Celery Beat cron keeps processing worker queues.
* **No Ordering Issues:** Database indices enforce sequential timestamps.
