"""Idempotent provider webhook ingestion and payment state changes."""

import logging
from datetime import timezone as datetime_timezone

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from ..errors import DomainError
from ..models import AuditEvent, Delivery, OutboxJob, Payment, Subscription, WebhookEvent
from .common import trace_id

logger = logging.getLogger(__name__)


def _parse_occurred_at(value):
    if value is None:
        return timezone.now()
    if not isinstance(value, str):
        raise DomainError("occurred_at must be an ISO-8601 string")
    parsed = parse_datetime(value)
    if parsed is None:
        raise DomainError("occurred_at must be a valid ISO-8601 timestamp")
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone=datetime_timezone.utc)
    return parsed


def _record_duplicate(event, delivery, payload, event_type, subscription_id, amount_cents, occurred_at):
    changed = (event.event_type, event.subscription_id, event.amount_cents) != (event_type, subscription_id, amount_cents)
    if "occurred_at" in payload and event.occurred_at != occurred_at:
        changed = True
    if changed:
        raise DomainError("provider_event_id was reused with a different payload", status_code=409, error_code="idempotency_conflict")
    WebhookEvent.objects.filter(pk=event.pk).update(duplicate_count=F("duplicate_count") + 1)
    Delivery.objects.filter(pk=delivery.pk).update(disposition="duplicate")
    AuditEvent.objects.create(trace_id=trace_id(), category="webhook.duplicate", message="Duplicate provider event ignored", metadata={"provider_event_id": event.provider_event_id})
    logger.info("Ignored duplicate webhook delivery", extra={"provider_event_id": event.provider_event_id})
    return {"disposition": "duplicate", "provider_event_id": event.provider_event_id, "applied": False}


def _apply_successful_payment(event_id, subscription, amount_cents, occurred_at):
    Payment.objects.create(provider_event_id=event_id, subscription=subscription, amount_cents=amount_cents, status=Payment.Status.SUCCEEDED, occurred_at=occurred_at)
    Subscription.objects.filter(pk=subscription.pk).update(status=Subscription.Status.ACTIVE, updated_at=timezone.now())
    return WebhookEvent.Status.PROCESSED


def _apply_failed_payment(event_id, subscription, amount_cents, occurred_at):
    Payment.objects.create(provider_event_id=event_id, subscription=subscription, amount_cents=amount_cents, status=Payment.Status.FAILED, occurred_at=occurred_at)
    Subscription.objects.filter(pk=subscription.pk).update(status=Subscription.Status.PAST_DUE, updated_at=timezone.now())
    OutboxJob.objects.get_or_create(
        event_key=f"retry:{event_id}",
        defaults={"kind": "payment.retry", "payload": {"provider_event_id": event_id, "subscription_id": subscription.pk, "amount_cents": amount_cents}},
    )
    return WebhookEvent.Status.RETRY_QUEUED


def _ignore_canceled_subscription(*_payment_details):
    return WebhookEvent.Status.IGNORED_CANCELED


_WEBHOOK_HANDLERS = {
    "payment.succeeded": _apply_successful_payment,
    "payment.failed": _apply_failed_payment,
}


def receive_webhook(payload):
    event_id = payload.get("provider_event_id")
    event_type = payload.get("event_type")
    subscription_id = payload.get("subscription_id")
    amount_cents = payload.get("amount_cents")
    if not all(isinstance(value, str) and value.strip() for value in (event_id, event_type, subscription_id)):
        raise DomainError("provider_event_id, event_type, and subscription_id are required")
    if event_type not in _WEBHOOK_HANDLERS:
        raise DomainError("event_type must be payment.succeeded or payment.failed")
    if not isinstance(amount_cents, int) or isinstance(amount_cents, bool) or amount_cents < 0:
        raise DomainError("amount_cents must be a non-negative integer")
    occurred_at = _parse_occurred_at(payload.get("occurred_at"))

    with transaction.atomic():
        try:
            subscription = Subscription.objects.select_for_update().get(pk=subscription_id)
        except Subscription.DoesNotExist:
            raise DomainError("subscription not found", status_code=404, error_code="subscription_not_found")

        delivery = Delivery.objects.create(provider_event_id=event_id)
        existing = WebhookEvent.objects.select_for_update().filter(provider_event_id=event_id).first()
        if existing:
            return _record_duplicate(existing, delivery, payload, event_type, subscription_id, amount_cents, occurred_at)

        try:
            with transaction.atomic():
                event = WebhookEvent.objects.create(
                    provider_event_id=event_id,
                    event_type=event_type,
                    subscription=subscription,
                    amount_cents=amount_cents,
                    occurred_at=occurred_at,
                    status=WebhookEvent.Status.RECEIVED,
                    payload=payload,
                )
        except IntegrityError:
            # A concurrent request may have inserted the unique event after our
            # initial lookup. The savepoint keeps the surrounding transaction usable.
            event = WebhookEvent.objects.select_for_update().get(provider_event_id=event_id)
            return _record_duplicate(event, delivery, payload, event_type, subscription_id, amount_cents, occurred_at)

        handler = _ignore_canceled_subscription if subscription.status == Subscription.Status.CANCELED else _WEBHOOK_HANDLERS[event_type]
        status = handler(event_id, subscription, amount_cents, occurred_at)

        WebhookEvent.objects.filter(pk=event.pk).update(status=status, processed_at=timezone.now())
        Delivery.objects.filter(pk=delivery.pk).update(disposition=status)
        AuditEvent.objects.create(trace_id=trace_id(), category="webhook.processed", message="Provider event applied", metadata={"provider_event_id": event_id, "status": status})
    return {"disposition": status, "provider_event_id": event_id, "applied": status != WebhookEvent.Status.IGNORED_CANCELED}
