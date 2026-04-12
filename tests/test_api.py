import unittest

try:
    from fastapi.testclient import TestClient
    from teacher_content_reminder.api import app
except Exception:  # pragma: no cover - optional dependency guard
    TestClient = None
    app = None


@unittest.skipIf(TestClient is None or app is None, "FastAPI test dependencies are not installed.")
class ApiTests(unittest.TestCase):
    def test_review_dashboard_and_queue_routes(self) -> None:
        client = TestClient(app)

        health = client.get("/healthz")
        review = client.get("/review")
        queue = client.get("/api/review-queue")
        activity = client.get("/api/activity-log")
        summary = client.get("/api/dashboard-summary")
        alerts = client.get("/alerts")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        self.assertEqual(review.status_code, 200)
        self.assertIn("Teacher Review Desk", review.text)
        self.assertIn("Run History", review.text)
        self.assertIn("summary-pending", review.text)
        self.assertIn("summary-alerts", review.text)
        self.assertIn("retry-send-button", review.text)
        self.assertIn("language-select", review.text)
        self.assertEqual(queue.status_code, 200)
        self.assertIsInstance(queue.json(), list)
        self.assertEqual(activity.status_code, 200)
        self.assertIsInstance(activity.json(), list)
        self.assertEqual(summary.status_code, 200)
        self.assertIn("queue_counts", summary.json())
        self.assertIn("schedule", summary.json())
        self.assertIn("weekday_only", summary.json()["schedule"])
        self.assertIn("beta_ops", summary.json())
        self.assertEqual(alerts.status_code, 200)


if __name__ == "__main__":
    unittest.main()
