"""Synthetic data scenarios used by the local lab."""

import uuid
from datetime import timedelta

from django.utils import timezone

from ..models import MetricObservation, Payment, Subscription
from .monitoring import record_metric
from .subscriptions import get_subscription
from .webhooks import receive_webhook


def seed_demo():
    subscription, _ = Subscription.objects.get_or_create(
        pk="sub_demo",
        defaults={"customer_id": "customer_demo", "plan": "trial-3-per-day", "amount_cents": 300, "status": Subscription.Status.ACTIVE},
    )
    Payment.objects.get_or_create(
        provider_event_id="evt_demo_seed",
        defaults={"subscription": subscription, "amount_cents": 300, "status": Payment.Status.SUCCEEDED},
    )
    if not MetricObservation.objects.filter(metric_name="payment_failure_rate", labels__source="synthetic_baseline").exists():
        baseline = [0.018,0.021,0.017,0.023,0.019,0.024,0.020,0.016,0.022,0.018,0.021,0.019,0.025,0.017,0.020,0.022,0.018,0.019,0.023,0.016,0.021,0.020,0.018,0.022]
        now = timezone.now()
        MetricObservation.objects.bulk_create([
            MetricObservation(metric_name="payment_failure_rate", value=value, sample_size=500, observed_at=now - timedelta(hours=24-index), labels={"source": "synthetic_baseline"})
            for index, value in enumerate(baseline)
        ])
    return {"seeded": True, "baseline_observations": 24, "demo_subscription_id": subscription.pk}


def inject_payment_spike():
    observation = record_metric("payment_failure_rate", 0.31, 500, {"source": "synthetic_failure_injection", "scenario": "provider_degradation"})
    return {"scenario": "provider_degradation", "observation": observation}


def inject_payment_failure():
    subscription = Subscription.objects.create(customer_id="customer_retry_demo", plan="retry-demo", amount_cents=300)
    result = receive_webhook({"provider_event_id": f"evt_fail_{uuid.uuid4().hex[:10]}", "event_type": "payment.failed", "subscription_id": subscription.pk, "amount_cents": subscription.amount_cents})
    return {"scenario": "retryable_payment_failure", "subscription": get_subscription(subscription.pk), "webhook": result}


def inject_duplicate_webhook():
    subscription = Subscription.objects.create(customer_id="customer_duplicate_demo", plan="duplicate-demo", amount_cents=300)
    payload = {"provider_event_id": f"evt_dup_{uuid.uuid4().hex[:10]}", "event_type": "payment.succeeded", "subscription_id": subscription.pk, "amount_cents": subscription.amount_cents}
    first = receive_webhook(payload)
    duplicate = receive_webhook(payload)
    return {"scenario": "duplicate_delivery", "first_delivery": first, "replay": duplicate, "subscription_id": subscription.pk}
