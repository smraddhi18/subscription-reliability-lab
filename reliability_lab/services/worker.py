"""Outbox retry processing and lease recovery."""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..models import AuditEvent, OutboxJob, Payment, Subscription
from .common import trace_id


def _fail_retry_job(job, payload, ignore_backoff):
    dead = job.attempts >= settings.MAX_RETRY_ATTEMPTS
    delay_seconds = settings.RETRY_BASE_SECONDS * (2 ** min(job.attempts - 1, 8))
    job.status = OutboxJob.Status.DEAD_LETTER if dead else OutboxJob.Status.PENDING
    now = timezone.now()
    job.next_attempt_at = now if ignore_backoff else now + timedelta(seconds=delay_seconds)
    job.last_error = "injected transient provider failure"
    job.updated_at = now
    job.save(update_fields=("attempts", "status", "next_attempt_at", "last_error", "updated_at"))
    if dead:
        AuditEvent.objects.create(trace_id=trace_id(), category="queue.dead_letter", message="Retry job exhausted attempts", metadata={"job_id": job.pk, "provider_event_id": payload["provider_event_id"]})


def _complete_retry_job(job, payload, _ignore_backoff):
    retry_event_id = f"retry_success:{payload['provider_event_id']}"
    Payment.objects.get_or_create(
        provider_event_id=retry_event_id,
        defaults={"subscription_id": payload["subscription_id"], "amount_cents": payload["amount_cents"], "status": Payment.Status.SUCCEEDED},
    )
    Subscription.objects.filter(pk=payload["subscription_id"], status=Subscription.Status.PAST_DUE).update(status=Subscription.Status.ACTIVE, updated_at=timezone.now())
    job.status = OutboxJob.Status.COMPLETED
    job.last_error = ""
    job.updated_at = timezone.now()
    job.save(update_fields=("attempts", "status", "last_error", "updated_at"))
    AuditEvent.objects.create(trace_id=trace_id(), category="queue.retry_succeeded", message="Payment retry completed", metadata={"job_id": job.pk, "provider_event_id": payload["provider_event_id"]})


_RETRY_HANDLERS = {True: _fail_retry_job, False: _complete_retry_job}


def run_worker(limit=20, force_failure=False, ignore_backoff=False):
    now = timezone.now()
    due = OutboxJob.objects.filter(status=OutboxJob.Status.PENDING)
    if not ignore_backoff:
        due = due.filter(next_attempt_at__lte=now)
    with transaction.atomic():
        jobs = list(due.select_for_update().order_by("created_at", "pk")[:limit])
        for job in jobs:
            job.status = OutboxJob.Status.PROCESSING
            job.updated_at = now
            job.save(update_fields=("status", "updated_at"))

    results = []
    for claimed in jobs:
        with transaction.atomic():
            job = OutboxJob.objects.select_for_update().get(pk=claimed.pk)
            if job.status != OutboxJob.Status.PROCESSING:
                continue
            job.attempts += 1
            payload = job.payload
            _RETRY_HANDLERS[bool(force_failure)](job, payload, ignore_backoff)
            results.append({"job_id": job.pk, "status": job.status, "attempt": job.attempts})
    return {"claimed": len(jobs), "results": results}


def simulate_worker_crash(limit=1):
    now = timezone.now()
    stale_time = now - timedelta(seconds=settings.WORKER_LEASE_SECONDS + 1)
    with transaction.atomic():
        jobs = list(OutboxJob.objects.filter(status=OutboxJob.Status.PENDING, next_attempt_at__lte=now).select_for_update().order_by("created_at", "pk")[:limit])
        OutboxJob.objects.filter(pk__in=[job.pk for job in jobs]).update(status=OutboxJob.Status.PROCESSING, updated_at=stale_time)
        if jobs:
            AuditEvent.objects.create(trace_id=trace_id(), category="queue.worker_crash_simulated", message="Worker stopped after claiming jobs", metadata={"job_ids": [job.pk for job in jobs]})
    return {"simulated_crash": True, "claimed_without_processing": [job.pk for job in jobs]}


def recover_processing_jobs():
    now = timezone.now()
    stale_before = now - timedelta(seconds=settings.WORKER_LEASE_SECONDS)
    with transaction.atomic():
        stale_ids = list(OutboxJob.objects.filter(status=OutboxJob.Status.PROCESSING, updated_at__lt=stale_before).values_list("pk", flat=True))
        recovered = OutboxJob.objects.filter(pk__in=stale_ids).update(
            status=OutboxJob.Status.PENDING, next_attempt_at=now, updated_at=now, last_error="recovered after worker restart",
        )
        if recovered:
            AuditEvent.objects.create(trace_id=trace_id(), category="queue.recovered", message="Expired processing leases returned to the queue", metadata={"count": recovered})
    return {"recovered": recovered}
