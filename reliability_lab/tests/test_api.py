"""End-to-end checks for the public API and cross-module workflows."""

import json

from django.test import TestCase

from reliability_lab.models import OutboxJob, Payment, Subscription, WebhookEvent


class ReliabilityApiTests(TestCase):
    def post_json(self, path, payload):
        return self.client.post(path, data=json.dumps(payload), content_type="application/json")

    def create_subscription(self):
        response = self.post_json(
            "/api/subscriptions",
            {"customer_id": "customer_1", "plan": "basic", "amount_cents": 300},
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["subscription"]["id"]

    def test_successful_webhook_is_idempotent_and_conflicting_replay_is_rejected(self):
        subscription_id = self.create_subscription()
        payload = {
            "provider_event_id": "evt_success_1",
            "event_type": "payment.succeeded",
            "subscription_id": subscription_id,
            "amount_cents": 300,
        }

        first = self.post_json("/api/webhooks", payload)
        replay = self.post_json("/api/webhooks", payload)
        conflict = self.post_json("/api/webhooks", {**payload, "amount_cents": 400})

        self.assertEqual(first.status_code, 202)
        self.assertTrue(first.json()["applied"])
        self.assertEqual(replay.json()["disposition"], "duplicate")
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["code"], "idempotency_conflict")
        self.assertEqual(Payment.objects.filter(provider_event_id="evt_success_1").count(), 1)
        self.assertEqual(WebhookEvent.objects.get(provider_event_id="evt_success_1").duplicate_count, 1)
        self.assertEqual(Subscription.objects.get(pk=subscription_id).status, Subscription.Status.ACTIVE)

    def test_failed_payment_recovery_and_retry(self):
        subscription_id = self.create_subscription()
        webhook = self.post_json("/api/webhooks", {
            "provider_event_id": "evt_failure_1",
            "event_type": "payment.failed",
            "subscription_id": subscription_id,
            "amount_cents": 300,
        })
        self.assertEqual(webhook.status_code, 202)
        self.assertEqual(Subscription.objects.get(pk=subscription_id).status, Subscription.Status.PAST_DUE)

        crash = self.post_json("/api/worker/crash", {})
        self.assertEqual(crash.status_code, 200)
        self.assertEqual(len(crash.json()["claimed_without_processing"]), 1)
        recovered = self.post_json("/api/worker/run?recover=true", {})
        self.assertEqual(recovered.json()["recovered"], 1)
        result = self.post_json("/api/worker/run", {})

        self.assertEqual(result.json()["results"][0]["status"], OutboxJob.Status.COMPLETED)
        self.assertEqual(Subscription.objects.get(pk=subscription_id).status, Subscription.Status.ACTIVE)
        self.assertEqual(Payment.objects.filter(subscription_id=subscription_id).count(), 2)

    def test_demo_spike_creates_evidence_linked_incident(self):
        self.assertEqual(self.post_json("/api/demo/seed", {}).status_code, 200)
        spike = self.post_json("/api/demo/payment-spike", {})
        self.assertEqual(spike.status_code, 201)
        anomaly = spike.json()["detection"]["anomalies"][0]

        analysis = self.post_json("/api/incidents/analyze", {"incident_id": anomaly["incident_id"]})
        evidence = self.client.get(f"/api/evidence/{anomaly['evidence_ids'][-1]}")

        self.assertEqual(analysis.status_code, 200)
        self.assertEqual(analysis.json()["analysis"]["analysis_mode"], "evidence_template")
        self.assertEqual(evidence.status_code, 200)
        self.assertEqual(evidence.json()["evidence_id"], anomaly["evidence_ids"][-1])

    def test_invalid_json_has_stable_error_code(self):
        response = self.client.post("/api/subscriptions", data="{", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_json")
