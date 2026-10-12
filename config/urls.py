from django.urls import path, re_path

from reliability_lab.api import core, demo, incidents, monitoring, payments, subscriptions, worker


urlpatterns = [
    path("", core.dashboard, name="dashboard"),
    path("health", core.health, name="health"),
    path("api/subscriptions", subscriptions.subscriptions, name="subscriptions"),
    path("api/webhooks", payments.webhooks, name="webhooks"),
    path("api/worker/run", worker.worker_run, name="worker-run"),
    path("api/worker/crash", worker.worker_crash, name="worker-crash"),
    path("api/metrics", monitoring.metrics, name="metrics"),
    path("api/reconcile", monitoring.reconcile, name="reconcile"),
    path("api/anomalies", incidents.anomalies, name="anomalies"),
    path("api/incidents", incidents.incidents, name="incidents"),
    path("api/incidents/analyze", incidents.analyze_incident, name="analyze-incident"),
    re_path(r"^api/evidence/(?P<evidence_id>metric:\d+|event:\d+|audit:\d+)$", incidents.evidence, name="evidence"),
    path("api/demo/seed", demo.demo_seed, name="demo-seed"),
    path("api/demo/payment-spike", demo.demo_payment_spike, name="demo-payment-spike"),
    path("api/demo/payment-failed", demo.demo_payment_failed, name="demo-payment-failed"),
    path("api/demo/duplicate-webhook", demo.demo_duplicate_webhook, name="demo-duplicate-webhook"),
]
