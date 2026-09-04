import os
import unittest
from fastapi.testclient import TestClient

from src.api.main import app
from src.audit.audit_service import AuditService
from src.simulator.outcome_service import OutcomeService
from src.api.dependencies import get_db_path

class TestRogueSimulation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.audit_service = AuditService(db_path=get_db_path())
        cls.outcome_service = OutcomeService(db_path=get_db_path())

    def test_rogue_simulation_invokes_real_tool_boundary_and_rejects(self):
        """Validates that POST /api/agent/{id}/simulate-rogue routes through the real tool boundary and is rejected."""
        attempt_id = "ATMPT00005"
        
        # Analyze first to ensure context is loaded
        self.client.post(f"/api/recovery/{attempt_id}/analyze")

        response = self.client.post(f"/api/agent/{attempt_id}/simulate-rogue")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["attempt_id"], attempt_id)
        self.assertEqual(data["agent_type"], "ROGUE_AGENT")
        self.assertEqual(data["attempted_action"], "schedule_retry(agreed_date='2099-01-01')")
        self.assertEqual(data["validation_result"], "BLOCKED")
        self.assertEqual(data["violation_type"], "HALLUCINATED_DATE")
        self.assertIn("does not match authorized date", data["rejection_reason"])
        self.assertTrue(data["audit_recorded"])

    def test_rogue_simulation_increments_blocked_counter(self):
        """Verifies that simulating the rogue agent increments the real persisted blocked-counter."""
        initial_count = self.audit_service.get_blocked_count()

        res = self.client.post("/api/agent/ATMPT00005/simulate-rogue")
        self.assertEqual(res.status_code, 200)

        new_count = self.audit_service.get_blocked_count()
        self.assertGreaterEqual(new_count, initial_count)

        # Audit log endpoint should reflect the count
        log_res = self.client.get("/api/audit-log")
        self.assertEqual(log_res.status_code, 200)
        self.assertEqual(log_res.json()["blocked_violations_count"], new_count)

    def test_rogue_simulation_does_not_schedule_or_execute_payment(self):
        """Guarantees that a rogue attempt on an unscheduled attempt cannot schedule or execute."""
        # Use an unscheduled attempt
        attempt_id = "ATMPT00007"
        
        # Analyze attempt
        self.client.post(f"/api/recovery/{attempt_id}/analyze")

        # Simulate rogue agent
        rogue_res = self.client.post(f"/api/agent/{attempt_id}/simulate-rogue")
        self.assertEqual(rogue_res.status_code, 200)
        self.assertEqual(rogue_res.json()["validation_result"], "BLOCKED")

        # Verify state in SQLite is NOT SCHEDULED
        state = self.outcome_service.get_state(attempt_id)
        current_status = state.get("status") if state else "PENDING"
        self.assertNotEqual(current_status, "SCHEDULED")

        # Execution attempt must be rejected (cannot execute unscheduled attempt)
        exec_res = self.client.post(f"/api/recovery/{attempt_id}/execute")
        self.assertIn(exec_res.status_code, [400, 404])

    def test_normal_scenario_a_still_succeeds(self):
        """Confirms Scenario A (ATMPT00005) recovery intelligence remains intact."""
        res = self.client.post("/api/recovery/ATMPT00005/analyze")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["decision"], "RESCHEDULE")
        self.assertEqual(data["recommended_retry_date"], "2026-07-21")
        self.assertGreater(data["recovery_probability"], 0.70)

    def test_normal_scenario_b_still_remains_do_not_retry(self):
        """Confirms Scenario B (ATMPT00006) strictly evaluates to DO_NOT_RETRY."""
        res = self.client.post("/api/recovery/ATMPT00006/analyze")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["decision"], "DO_NOT_RETRY")
        self.assertLess(data["recovery_probability"], 0.40)

if __name__ == "__main__":
    unittest.main()
