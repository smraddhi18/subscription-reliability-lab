"""Subscription creation and lookup."""

from django.db import transaction

from ..errors import DomainError
from ..models import AuditEvent, Subscription


def create_subscription(customer_id, plan, amount_cents):
    if not isinstance(customer_id, str) or not customer_id.strip() or not isinstance(plan, str) or not plan.strip():
        raise DomainError("customer_id and plan are required")
    if not isinstance(amount_cents, int) or isinstance(amount_cents, bool) or amount_cents < 0:
        raise DomainError("amount_cents must be a non-negative integer")
    with transaction.atomic():
        subscription = Subscription.objects.create(
            customer_id=customer_id.strip(), plan=plan.strip(), amount_cents=amount_cents,
        )
        AuditEvent.objects.create(trace_id=subscription.pk, category="subscription.created", message="Trial subscription created", metadata={"plan": plan})
    return subscription.as_dict()


def get_subscription(subscription_id):
    try:
        return Subscription.objects.get(pk=subscription_id).as_dict()
    except Subscription.DoesNotExist:
        return None


def list_subscriptions(limit=100):
    return [item.as_dict() for item in Subscription.objects.all()[:limit]]
