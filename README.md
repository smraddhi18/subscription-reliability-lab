# Subscription Reliability Lab

A runnable Django backend lab for subscription state, payment webhook reliability, queue recovery, reconciliation, anomaly detection, and AI-assisted incident analysis.

All persistence reads and writes use Django ORM models and querysets. SQLite is the default local database; PostgreSQL can be enabled through environment settings.

## Code layout

- `reliability_lab/models.py` defines the database entities and constraints.
- `reliability_lab/services/` groups application workflows by subscription, webhook, worker, monitoring, and demo scenario. Transaction boundaries stay in the services.
- `reliability_lab/api/` contains thin HTTP handlers. `common.py` owns JSON parsing and public error responses.
- `reliability_lab/detection.py` and `incident_analysis.py` handle anomaly detection and evidence-linked analysis.
- `config/urls.py` maps the existing API paths to the handlers.
- `reliability_lab/tests/` covers the main workflows through the HTTP API.

Run `python manage.py test reliability_lab` after installing the requirements. The service package also exports its original public functions for existing imports.

Expected failures use typed `DomainError` exceptions with stable HTTP status and error codes. Unexpected failures are logged server-side and returned through a generic `GenericException` response that does not expose internal details. Event, retry, and evidence behavior is dispatched through handler maps to keep branching localized.

## Run it

Requires Python 3.11 or newer.

```bash
cd subscription-reliability-lab
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8080
```

Or run `./run.sh` after installing the requirements; it applies migrations and starts the local server.

Open [http://localhost:8080](http://localhost:8080). The dashboard has buttons to seed a baseline, inject a payment-failure spike, run the worker, reconcile records, and generate an incident analysis. The API is also usable directly with `curl`.

The default database is `data/reliability.db`. Set `RELIABILITY_DB` to use a different path. No external service or model credential is needed for the local demo.

For PostgreSQL, set `DB_ENGINE=postgres` and `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT` before running migrations.

## Optional LLM analyst

Incident analysis always has a deterministic, evidence-linked fallback. To use an OpenAI-compatible chat-completions endpoint, set:

```bash
export LLM_BASE_URL=https://api.example.com/v1
export LLM_API_KEY=your-key
export LLM_MODEL=your-model
```

The analyst receives a fixed evidence bundle and has no tools or write access. It cannot change subscriptions, payments, or queue state. Logs are treated as untrusted evidence. Leave these settings unset for a fully local demo.

## API overview

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Process and database health |
| `GET` | `/api/subscriptions` | List subscriptions |
| `POST` | `/api/subscriptions` | Create a trial subscription |
| `POST` | `/api/webhooks` | Accept an idempotent payment event |
| `POST` | `/api/worker/run` | Process due retry jobs |
| `GET` | `/api/metrics` | Reliability and queue metrics |
| `POST` | `/api/reconcile` | Compare payment ledger and subscription state |
| `GET` | `/api/anomalies` | Score recent metric observations |
| `GET` | `/api/incidents` | List incidents and stored analyses |
| `GET` | `/api/evidence/{kind}:{id}` | Retrieve a cited metric, event, or audit record |
| `POST` | `/api/incidents/analyze` | Generate a read-only incident analysis |
| `POST` | `/api/demo/seed` | Seed a synthetic baseline and demo subscription |
| `POST` | `/api/demo/payment-spike` | Add an anomalous payment-failure observation |
| `POST` | `/api/demo/payment-failed` | Create a subscription and retryable failed payment |
| `POST` | `/api/demo/duplicate-webhook` | Deliver one successful provider event twice |
| `POST` | `/api/worker/crash` | Simulate a worker exit after claiming a due job |

Example webhook payload:

```json
{
  "provider_event_id": "evt_demo_001",
  "event_type": "payment.succeeded",
  "subscription_id": "sub_demo",
  "amount_cents": 300,
  "occurred_at": "2026-09-28T12:00:00Z"
}
```

Send the same `provider_event_id` again to see the idempotency guard count the duplicate without applying the payment twice.

## Reliability behavior

- Webhook receipt and state transition happen in one Django `transaction.atomic()` block.
- Provider event IDs and payment ledger entries are unique, so retries do not double-apply a payment.
- Failed payments create an outbox job. Jobs use capped exponential backoff and move to the dead-letter state after the configured attempt limit.
- The worker claims due jobs transactionally with ORM row locking where the database supports it, then records each attempt.
- Reconciliation reports dangling payment references, amount mismatches, and active subscriptions without a successful ledger entry.
- The anomaly detector compares the newest observation with a historical baseline using a robust median/MAD score and a minimum absolute threshold.
- The incident analyst cites evidence IDs from the metric and event store. Its configured LLM mode is read-only and has no tool-calling path.

## Design limits

This is a portfolio lab, not a payment processor. The local demo uses SQLite and a single-process worker. Production deployment would require PostgreSQL, a separate durable queue, authentication, provider signature verification, and operational controls. The synthetic demo data is clearly marked and should not be mistaken for real customer or revenue data.

## Suggested demo

1. Click **Seed demo** and inspect `/api/metrics`.
2. Click **Inject failure spike** and inspect `/api/anomalies`.
3. Click **Analyze incident** and follow each cited evidence ID to `/api/evidence/{id}`.
4. Create a subscription, send a successful webhook twice, and verify the duplicate count and single ledger entry.
5. Create a retry job, simulate a worker crash, and recover the expired lease after restart.
6. Simulate repeated provider failures with `{"force_failure":true,"ignore_backoff":true}` at `/api/worker/run` until the job reaches dead letter.

The retry worker uses deterministic provider outcomes for the demo. It models bounded retries and queue state transitions; it does not send real charges or call a payment provider.
