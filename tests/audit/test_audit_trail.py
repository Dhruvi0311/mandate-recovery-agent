import os
import unittest
from fastapi.testclient import TestClient

from src.api.main import app
from src.audit.audit_service import AuditService
from src.api.dependencies import get_db_path

class TestAuditTrail(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.audit_service = AuditService(db_path=get_db_path())

    def test_get_audit_log_endpoint_returns_records(self):
        """Validates that GET /api/audit-log returns 200 with structured audit list."""
        response = self.client.get("/api/audit-log")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("total_records", data)
        self.assertIn("blocked_violations_count", data)
        self.assertIn("records", data)
        self.assertIsInstance(data["records"], list)
        self.assertGreater(data["total_records"], 0)

        first = data["records"][0]
        required_fields = [
            "attempt_id", "customer_id", "mandate_id", "timestamp",
            "decision", "reason_codes", "recovery_probability",
            "recommended_retry_date", "consent_requirement", "consent_status",
            "validation_result", "execution_outcome", "lifecycle_status",
            "is_blocked", "timeline"
        ]
        for field in required_fields:
            self.assertIn(field, first, f"Field '{field}' missing from audit record")

    def test_attempt_specific_filtering_and_not_found(self):
        """Validates GET /api/audit-log/{attempt_id} and query parameter filtering."""
        # 1. Direct path parameter
        res_direct = self.client.get("/api/audit-log/ATMPT00005")
        self.assertEqual(res_direct.status_code, 200)
        rec = res_direct.json()
        self.assertEqual(rec["attempt_id"], "ATMPT00005")

        # 2. Query param filtering
        res_filter = self.client.get("/api/audit-log?attempt_id=ATMPT00005")
        self.assertEqual(res_filter.status_code, 200)
        filter_data = res_filter.json()
        self.assertGreater(len(filter_data["records"]), 0)
        self.assertEqual(filter_data["records"][0]["attempt_id"], "ATMPT00005")

        # 3. 404 on nonexistent
        res_404 = self.client.get("/api/audit-log/NON_EXISTENT_ATTEMPT_9999")
        self.assertEqual(res_404.status_code, 404)

    def test_ground_truth_isolation(self):
        """Guarantees ground_truth_recoverable and ground_truth_retry_date are never exposed."""
        response = self.client.get("/api/audit-log")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        prohibited = [
            "ground_truth_recoverable",
            "ground_truth_retry_date",
            "actual_retry_result",
            "scenario_tag"
        ]
        for rec in data["records"]:
            for key in prohibited:
                self.assertNotIn(key, rec, f"Prohibited key '{key}' leaked into audit record!")

    def test_blocked_invalid_action_increments_counter(self):
        """Validates that a recorded blocked action increments the blocked violations counter."""
        initial_count = self.audit_service.get_blocked_count()

        # Record a simulated rogue hallucinated date action
        test_attempt_id = f"TEST_ROGUE_{os.urandom(4).hex()}"
        self.audit_service.record_action_attempt(
            attempt_id=test_attempt_id,
            customer_id="CUST_TEST",
            mandate_id="MAND_TEST",
            customer_response="Yes, schedule it",
            consent_status="GRANTED",
            requested_action="schedule_retry(agreed_date='2099-01-01')",
            validation_result="BLOCKED",
            validation_details="Agreed date 2099-01-01 does not match authorized date 2026-07-01.",
            is_blocked=True,
            violation_type="HALLUCINATED_DATE",
            lifecycle_status="ACTION_REJECTED"
        )

        new_count = self.audit_service.get_blocked_count()
        self.assertEqual(new_count, initial_count + 1)

        # Verify endpoint reflects the incremented counter
        response = self.client.get("/api/audit-log")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["blocked_violations_count"], new_count)

    def test_valid_consented_action_does_not_increment_blocked_counter(self):
        """Validates that a legitimate, consented action does not increment the blocked counter."""
        initial_count = self.audit_service.get_blocked_count()

        test_attempt_id = f"TEST_VALID_{os.urandom(4).hex()}"
        self.audit_service.record_action_attempt(
            attempt_id=test_attempt_id,
            customer_id="CUST_TEST",
            mandate_id="MAND_TEST",
            customer_response="Yes, please schedule for 2026-07-21",
            consent_status="GRANTED",
            requested_action="schedule_retry(agreed_date='2026-07-21')",
            validation_result="ACCEPTED",
            validation_details="Authorized retry date and active customer consent verified.",
            is_blocked=False,
            violation_type=None,
            lifecycle_status="SCHEDULED"
        )

        new_count = self.audit_service.get_blocked_count()
        self.assertEqual(new_count, initial_count)

    def test_rogue_retry_date_recorded_as_blocked(self):
        """Verifies that an attempt with a rogue hallucinated date is stored as BLOCKED with HALLUCINATED_DATE."""
        test_attempt_id = f"TEST_ROGUE_DATE_{os.urandom(4).hex()}"
        self.audit_service.record_action_attempt(
            attempt_id=test_attempt_id,
            customer_id="CUST_ROGUE",
            mandate_id="MAND_ROGUE",
            customer_response="Yes",
            consent_status="GRANTED",
            requested_action="schedule_retry(2099-01-01)",
            validation_result="BLOCKED",
            validation_details="Cannot schedule retry: Agreed date 2099-01-01 does not match authorized date 2026-07-01.",
            is_blocked=True,
            violation_type="HALLUCINATED_DATE",
            lifecycle_status="ACTION_REJECTED"
        )

        rec = self.audit_service.get_record(test_attempt_id)
        self.assertIsNotNone(rec)
        self.assertTrue(rec["is_blocked"])
        self.assertEqual(rec["validation_result"], "BLOCKED")
        self.assertEqual(rec["violation_type"], "HALLUCINATED_DATE")
        self.assertIn("does not match authorized date", rec["validation_details"])

    def test_missing_consent_recorded_as_blocked(self):
        """Verifies that an action attempted without customer consent is stored as BLOCKED with CONSENT_VIOLATION."""
        test_attempt_id = f"TEST_NO_CONSENT_{os.urandom(4).hex()}"
        self.audit_service.record_action_attempt(
            attempt_id=test_attempt_id,
            customer_id="CUST_NO_CONSENT",
            mandate_id="MAND_NO_CONSENT",
            customer_response="No, cancel",
            consent_status="REJECTED",
            requested_action="schedule_retry(2026-07-01)",
            validation_result="BLOCKED",
            validation_details="Cannot schedule retry: Customer consent was not granted.",
            is_blocked=True,
            violation_type="CONSENT_VIOLATION",
            lifecycle_status="ACTION_REJECTED"
        )

        rec = self.audit_service.get_record(test_attempt_id)
        self.assertIsNotNone(rec)
        self.assertTrue(rec["is_blocked"])
        self.assertEqual(rec["validation_result"], "BLOCKED")
        self.assertEqual(rec["violation_type"], "CONSENT_VIOLATION")
        self.assertIn("Customer consent was not granted", rec["validation_details"])

    def test_ambiguous_response_does_not_create_unauthorized_state_change(self):
        """Verifies that an ambiguous customer inquiry does not grant consent or schedule retry."""
        test_attempt_id = "ATMPT00007"
        
        # Analyze first
        self.client.post(f"/api/recovery/{test_attempt_id}/analyze")
        
        # Send ambiguous message
        res = self.client.post(f"/api/agent/{test_attempt_id}/message", json={"message": "Can you explain what this payment is?"})
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Consent must remain false, action_status must not be COMPLETED
        self.assertFalse(data["consent_granted"])
        self.assertNotEqual(data["recovery_state"], "SCHEDULED")
        self.assertNotEqual(data["action_status"], "COMPLETED")

if __name__ == "__main__":
    unittest.main()
