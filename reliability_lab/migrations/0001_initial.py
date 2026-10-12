import django.db.models.deletion
import django.utils.timezone
import reliability_lab.models
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.CharField(default=reliability_lab.models.new_subscription_id, editable=False, max_length=32, primary_key=True, serialize=False)),
                ("customer_id", models.CharField(db_index=True, max_length=128)),
                ("plan", models.CharField(max_length=80)),
                ("amount_cents", models.PositiveIntegerField()),
                ("status", models.CharField(choices=[("trialing", "Trialing"), ("active", "Active"), ("past_due", "Past due"), ("canceled", "Canceled")], db_index=True, default="trialing", max_length=16)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("updated_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("trace_id", models.CharField(db_index=True, max_length=40)),
                ("category", models.CharField(db_index=True, max_length=80)),
                ("message", models.CharField(max_length=240)),
                ("metadata", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
        migrations.CreateModel(
            name="Delivery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider_event_id", models.CharField(db_index=True, max_length=160)),
                ("delivered_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("disposition", models.CharField(default="received", max_length=32)),
            ],
        ),
        migrations.CreateModel(
            name="Incident",
            fields=[
                ("id", models.CharField(default=reliability_lab.models.new_incident_id, editable=False, max_length=32, primary_key=True, serialize=False)),
                ("kind", models.CharField(db_index=True, max_length=64)),
                ("severity", models.CharField(max_length=16)),
                ("title", models.CharField(max_length=240)),
                ("status", models.CharField(db_index=True, default="open", max_length=16)),
                ("opened_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("evidence", models.JSONField(default=list)),
                ("analysis", models.JSONField(blank=True, null=True)),
            ],
            options={"ordering": ("-opened_at",)},
        ),
        migrations.CreateModel(
            name="MetricObservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("metric_name", models.CharField(db_index=True, max_length=80)),
                ("value", models.FloatField()),
                ("sample_size", models.PositiveIntegerField()),
                ("observed_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("labels", models.JSONField(default=dict)),
            ],
            options={"ordering": ("-observed_at", "-id")},
        ),
        migrations.CreateModel(
            name="OutboxJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_key", models.CharField(max_length=180, unique=True)),
                ("kind", models.CharField(max_length=48)),
                ("payload", models.JSONField(default=dict)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("processing", "Processing"), ("completed", "Completed"), ("dead_letter", "Dead letter")], db_index=True, default="pending", max_length=16)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("next_attempt_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("updated_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("last_error", models.TextField(blank=True, default="")),
            ],
            options={"ordering": ("created_at", "id")},
        ),
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.CharField(default=reliability_lab.models.new_payment_id, editable=False, max_length=32, primary_key=True, serialize=False)),
                ("provider_event_id", models.CharField(max_length=180, unique=True)),
                ("amount_cents", models.PositiveIntegerField()),
                ("status", models.CharField(choices=[("succeeded", "Succeeded"), ("failed", "Failed")], db_index=True, max_length=16)),
                ("occurred_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("subscription", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="reliability_lab.subscription")),
            ],
            options={"ordering": ("-occurred_at",)},
        ),
        migrations.CreateModel(
            name="WebhookEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider_event_id", models.CharField(max_length=160, unique=True)),
                ("event_type", models.CharField(max_length=40)),
                ("amount_cents", models.PositiveIntegerField()),
                ("occurred_at", models.DateTimeField()),
                ("received_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(choices=[("received", "Received"), ("processed", "Processed"), ("retry_queued", "Retry queued"), ("ignored_canceled", "Ignored for canceled subscription")], default="received", max_length=24)),
                ("duplicate_count", models.PositiveIntegerField(default=0)),
                ("payload", models.JSONField(default=dict)),
                ("subscription", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="webhook_events", to="reliability_lab.subscription")),
            ],
            options={"ordering": ("-received_at", "-id")},
        ),
        migrations.AddIndex(model_name="subscription", index=models.Index(fields=["status", "updated_at"], name="sub_status_updated_idx")),
        migrations.AddIndex(model_name="outboxjob", index=models.Index(fields=["status", "next_attempt_at"], name="outbox_due_idx")),
        migrations.AddIndex(model_name="metricobservation", index=models.Index(fields=["metric_name", "observed_at"], name="metric_recent_idx")),
        migrations.AddIndex(model_name="payment", index=models.Index(fields=["subscription", "status"], name="payment_sub_status_idx")),
        migrations.AddConstraint(model_name="incident", constraint=models.UniqueConstraint(condition=models.Q(("status", "open")), fields=("kind",), name="one_open_incident_per_kind")),
    ]

