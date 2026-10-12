import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone


def new_subscription_id():
    return f"sub_{uuid.uuid4().hex[:12]}"


def new_payment_id():
    return f"pay_{uuid.uuid4().hex[:12]}"


def new_incident_id():
    return f"inc_{uuid.uuid4().hex[:12]}"


class Subscription(models.Model):
    class Status(models.TextChoices):
        TRIALING = "trialing", "Trialing"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past due"
        CANCELED = "canceled", "Canceled"

    id = models.CharField(primary_key=True, max_length=32, default=new_subscription_id, editable=False)
    customer_id = models.CharField(max_length=128, db_index=True)
    plan = models.CharField(max_length=80)
    amount_cents = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.TRIALING, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("status", "updated_at"), name="sub_status_updated_idx")]

    def as_dict(self):
        return {"id": self.id, "customer_id": self.customer_id, "plan": self.plan, "amount_cents": self.amount_cents, "status": self.status, "created_at": self.created_at.isoformat(), "updated_at": self.updated_at.isoformat()}


class WebhookEvent(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        PROCESSED = "processed", "Processed"
        RETRY_QUEUED = "retry_queued", "Retry queued"
        IGNORED_CANCELED = "ignored_canceled", "Ignored for canceled subscription"

    provider_event_id = models.CharField(max_length=160, unique=True)
    event_type = models.CharField(max_length=40)
    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT, related_name="webhook_events")
    amount_cents = models.PositiveIntegerField()
    occurred_at = models.DateTimeField()
    received_at = models.DateTimeField(default=timezone.now, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.RECEIVED)
    duplicate_count = models.PositiveIntegerField(default=0)
    payload = models.JSONField(default=dict)

    class Meta:
        ordering = ("-received_at", "-id")


class Delivery(models.Model):
    provider_event_id = models.CharField(max_length=160, db_index=True)
    delivered_at = models.DateTimeField(default=timezone.now, db_index=True)
    disposition = models.CharField(max_length=32, default="received")


class Payment(models.Model):
    class Status(models.TextChoices):
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    id = models.CharField(primary_key=True, max_length=32, default=new_payment_id, editable=False)
    provider_event_id = models.CharField(max_length=180, unique=True)
    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT, related_name="payments")
    amount_cents = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, db_index=True)
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-occurred_at",)
        indexes = [models.Index(fields=("subscription", "status"), name="payment_sub_status_idx")]


class OutboxJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        DEAD_LETTER = "dead_letter", "Dead letter"

    event_key = models.CharField(max_length=180, unique=True)
    kind = models.CharField(max_length=48)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("created_at", "id")
        indexes = [models.Index(fields=("status", "next_attempt_at"), name="outbox_due_idx")]


class MetricObservation(models.Model):
    metric_name = models.CharField(max_length=80, db_index=True)
    value = models.FloatField()
    sample_size = models.PositiveIntegerField()
    observed_at = models.DateTimeField(default=timezone.now, db_index=True)
    labels = models.JSONField(default=dict)

    class Meta:
        ordering = ("-observed_at", "-id")
        indexes = [models.Index(fields=("metric_name", "observed_at"), name="metric_recent_idx")]


class Incident(models.Model):
    id = models.CharField(primary_key=True, max_length=32, default=new_incident_id, editable=False)
    kind = models.CharField(max_length=64, db_index=True)
    severity = models.CharField(max_length=16)
    title = models.CharField(max_length=240)
    status = models.CharField(max_length=16, default="open", db_index=True)
    opened_at = models.DateTimeField(default=timezone.now, db_index=True)
    evidence = models.JSONField(default=list)
    analysis = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ("-opened_at",)
        constraints = [models.UniqueConstraint(fields=("kind",), condition=Q(status="open"), name="one_open_incident_per_kind")]


class AuditEvent(models.Model):
    trace_id = models.CharField(max_length=40, db_index=True)
    category = models.CharField(max_length=80, db_index=True)
    message = models.CharField(max_length=240)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ("-created_at", "-id")
