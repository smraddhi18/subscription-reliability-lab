"""Operational metrics and ledger reconciliation."""

from django.db.models import Count, Exists, F, OuterRef, Q, Sum
from django.utils import timezone

from ..errors import DomainError
from ..models import Incident, MetricObservation, OutboxJob, Payment, Subscription, WebhookEvent


def metrics():
    subscription_counts = {item["status"]: item["total"] for item in Subscription.objects.values("status").annotate(total=Count("pk"))}
    queue_counts = {item["status"]: item["total"] for item in OutboxJob.objects.values("status").annotate(total=Count("pk"))}
    payment_totals = Payment.objects.aggregate(
        total=Count("pk"),
        failures=Count("pk", filter=Q(status=Payment.Status.FAILED)),
    )
    payment_failure_rate = round(payment_totals["failures"] / payment_totals["total"], 4) if payment_totals["total"] else 0.0
    return {
        "subscriptions": subscription_counts,
        "webhook_events": WebhookEvent.objects.count(),
        "duplicate_deliveries": WebhookEvent.objects.aggregate(total=Sum("duplicate_count"))["total"] or 0,
        "payment_failure_rate": payment_failure_rate,
        "queue": queue_counts,
        "dead_letter_jobs": OutboxJob.objects.filter(status=OutboxJob.Status.DEAD_LETTER).count(),
        "open_incidents": Incident.objects.filter(status="open").count(),
    }


def reconcile():
    dangling_payments = Payment.objects.filter(subscription__isnull=True).values("id", "provider_event_id", "subscription_id")
    mismatches = [{"kind": "dangling_payment", **item} for item in dangling_payments]
    amount_mismatches = Payment.objects.filter(status=Payment.Status.SUCCEEDED).annotate(expected_cents=F("subscription__amount_cents")).exclude(amount_cents=F("expected_cents")).values("id", "provider_event_id", "subscription_id", "amount_cents", "expected_cents")
    mismatches.extend({"kind": "amount_mismatch", **item} for item in amount_mismatches)
    successful_payment = Payment.objects.filter(subscription_id=OuterRef("pk"), status=Payment.Status.SUCCEEDED)
    unbacked_active = Subscription.objects.filter(status=Subscription.Status.ACTIVE).annotate(has_payment=Exists(successful_payment)).filter(has_payment=False).values("id", "status")
    mismatches.extend({"kind": "active_without_payment", "subscription_id": item["id"], "status": item["status"]} for item in unbacked_active)
    return {"checked_at": timezone.now().isoformat(), "mismatch_count": len(mismatches), "mismatches": mismatches}


def record_metric(name, value, sample_size, labels=None):
    if not isinstance(name, str) or not name or not isinstance(sample_size, int) or isinstance(sample_size, bool) or sample_size < 0:
        raise DomainError("metric_name and a non-negative integer sample_size are required")
    observation = MetricObservation.objects.create(metric_name=name, value=float(value), sample_size=sample_size, labels=labels or {})
    return {"id": observation.pk, "metric_name": observation.metric_name, "value": observation.value, "sample_size": observation.sample_size, "observed_at": observation.observed_at.isoformat(), "labels": observation.labels}
