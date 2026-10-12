import statistics

from django.conf import settings
from django.db import transaction

from .models import AuditEvent, Incident, MetricObservation, WebhookEvent


def _robust_score(value, baseline):
    center = statistics.median(baseline)
    mad = statistics.median(abs(item - center) for item in baseline)
    scale = max(1.4826 * mad, 0.005)
    return center, (value - center) / scale


def detect():
    observations = list(MetricObservation.objects.filter(metric_name="payment_failure_rate").order_by("-observed_at", "-pk")[:25])
    observations.reverse()
    if len(observations) < 8:
        return {"status": "insufficient_data", "required": 8, "available": len(observations), "anomalies": []}

    baseline = [item.value for item in observations[:-1]]
    latest = observations[-1]
    center, score = _robust_score(latest.value, baseline)
    if score < settings.ANOMALY_Z_THRESHOLD or latest.value < settings.ANOMALY_MIN_RATE:
        return {"status": "analyzed", "observations": len(observations), "anomalies": []}

    evidence = [f"metric:{item.pk}" for item in observations[-5:]]
    severity = "critical" if latest.value >= 0.25 else "high"
    title = f"Payment failure rate elevated to {latest.value:.1%}"
    with transaction.atomic():
        incident, created = Incident.objects.get_or_create(
            kind="payment_failure_spike",
            status="open",
            defaults={"severity": severity, "title": title, "evidence": evidence},
        )
        if not created:
            incident.severity = severity
            incident.title = title
            incident.evidence = evidence
            incident.save(update_fields=("severity", "title", "evidence"))
    anomaly = {
        "incident_id": incident.pk,
        "kind": incident.kind,
        "severity": incident.severity,
        "title": incident.title,
        "value": latest.value,
        "baseline_median": round(center, 4),
        "robust_z_score": round(score, 2),
        "evidence_ids": evidence,
    }
    return {"status": "analyzed", "observations": len(observations), "anomalies": [anomaly]}


def incident_list():
    return [
        {"id": incident.pk, "kind": incident.kind, "severity": incident.severity, "title": incident.title,
         "status": incident.status, "opened_at": incident.opened_at.isoformat(),
         "evidence": incident.evidence, "analysis": incident.analysis}
        for incident in Incident.objects.all()[:50]
    ]


def _metric_evidence(item):
    return {"id": item.pk, "metric_name": item.metric_name, "value": item.value, "sample_size": item.sample_size, "observed_at": item.observed_at.isoformat(), "labels": item.labels}


def _event_evidence(item):
    return {"id": item.pk, "provider_event_id": item.provider_event_id, "event_type": item.event_type, "subscription_id": item.subscription_id, "amount_cents": item.amount_cents, "status": item.status, "duplicate_count": item.duplicate_count, "received_at": item.received_at.isoformat()}


def _audit_evidence(item):
    return {"id": item.pk, "category": item.category, "message": item.message, "metadata": item.metadata, "created_at": item.created_at.isoformat()}


_EVIDENCE_LOOKUPS = {
    "metric": (MetricObservation, _metric_evidence, {}),
    "event": (WebhookEvent, _event_evidence, {"select_related": ("subscription",)}),
    "audit": (AuditEvent, _audit_evidence, {}),
}


def get_evidence(evidence_id):
    try:
        kind, raw_id = evidence_id.split(":", 1)
        record_id = int(raw_id)
    except (ValueError, AttributeError):
        return None
    lookup = _EVIDENCE_LOOKUPS.get(kind)
    if lookup is None:
        return None
    model, serializer, options = lookup
    item = model.objects.filter(pk=record_id).select_related(*options.get("select_related", ())).first()
    if item is None:
        return None
    return {"evidence_id": evidence_id, "kind": kind, "record": serializer(item)}
