import os
import unittest
import pandas as pd
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.dependencies import get_outcome_service, get_conversation_store, OutcomeService, ConversationStore

class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        df = pd.read_csv("data/mandate_attempts.csv")
        failed = df[df["status"] == "FAILED"]["attempt_id"].tolist()
        cls.valid_attempt_id = failed[0] if failed else "ATMPT00005"
        cls.second_attempt_id = failed[1] if len(failed) > 1 else "ATMPT00006"
        cls.third_attempt_id = failed[2] if len(failed) > 2 else "ATMPT00007"

    def setUp(self):
        self.invalid_attempt_id = "NON_EXISTENT_9999"

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "mandate-recovery-agent")

    def test_get_mandates_list_and_ground_truth_isolation(self):
        response = self.client.get("/api/mandates")
        self.assertEqual(response.status_code, 200)
        items = response.json()
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 0)

        prohibited_keys = {
            "ground_truth_recoverable",
            "ground_truth_retry_date",
            "actual_retry_result",
            "customer_response",
            "scenario_tag"
        }

        for item in items[:10]:
            self.assertIn("attempt_id", item)
            self.assertIn("amount", item)
            self.assertIn("recovery_state", item)
            # Ensure ground truth is NEVER exposed
            for key in prohibited_keys:
                self.assertNotIn(key, item)

    def test_get_mandate_detail(self):
        response = self.client.get(f"/api/mandates/{self.valid_attempt_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["attempt_id"], self.valid_attempt_id)
        self.assertIn("merchant_name", data)
        self.assertIn("amount", data)
        self.assertIn("recovery_state", data)
        self.assertNotIn("ground_truth_recoverable", data)
        self.assertNotIn("ground_truth_retry_date", data)

    def test_get_mandate_detail_not_found(self):
        response = self.client.get(f"/api/mandates/{self.invalid_attempt_id}")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("detail", data)

    def test_recovery_analysis(self):
        response = self.client.post(f"/api/recovery/{self.valid_attempt_id}/analyze")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["attempt_id"], self.valid_attempt_id)
        self.assertIn("recovery_probability", data)
        self.assertIn("decision", data)
        self.assertIn("reason_codes", data)
        self.assertIn("candidate_retry_windows", data)
        self.assertIn("requires_customer_consent", data)
        
        # Verify ground-truth isolation
        self.assertNotIn("ground_truth_recoverable", data)
        self.assertNotIn("ground_truth_retry_date", data)

    def test_recovery_analysis_not_found(self):
        response = self.client.post(f"/api/recovery/{self.invalid_attempt_id}/analyze")
        self.assertEqual(response.status_code, 404)

    def test_recovery_status_pending(self):
        response = self.client.get(f"/api/recovery/{self.valid_attempt_id}/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["attempt_id"], self.valid_attempt_id)
        self.assertIn(data["status"], ["PENDING", "SCHEDULED", "EXECUTED", "ACTION_REJECTED"])

    def test_recovery_status_not_found(self):
        response = self.client.get(f"/api/recovery/{self.invalid_attempt_id}/status")
        self.assertEqual(response.status_code, 404)

    def test_agent_multi_turn_conversation_and_scheduling(self):
        attempt_id = self.valid_attempt_id
        
        # Turn 1: Initial query/greeting
        res1 = self.client.post(f"/api/agent/{attempt_id}/message", json={"message": "What is the status of my mandate?"})
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1["attempt_id"], attempt_id)
        self.assertIsInstance(data1["messages"], list)
        self.assertGreaterEqual(len(data1["messages"]), 2) # Customer message + Agent response
        self.assertFalse(data1["consent_granted"])

        # Turn 2: Customer consents
        res2 = self.client.post(f"/api/agent/{attempt_id}/message", json={"message": "Yes, please schedule it"})
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertTrue(data2["consent_granted"])
        # Multi-turn state must preserve earlier messages
        self.assertGreater(len(data2["messages"]), len(data1["messages"]))
        
        # Verify status endpoint reflects updated state
        status_res = self.client.get(f"/api/recovery/{attempt_id}/status")
        self.assertEqual(status_res.status_code, 200)
        status_data = status_res.json()
        self.assertIn(status_data["status"], ["SCHEDULED", "ACTION_REJECTED", "COMPLETED", "FAILED"])

    def test_execution_unauthorized_when_not_scheduled(self):
        # Attempt that is definitely not in SCHEDULED state
        unscheduled_attempt = self.second_attempt_id
        # Reset or ensure state is not scheduled
        outcome_service = get_outcome_service()
        state = outcome_service.get_state(unscheduled_attempt)
        if state and state.get("status") == "SCHEDULED":
            outcome_service.update_state(unscheduled_attempt, "CUST", "PENDING")
            
        res = self.client.post(f"/api/recovery/{unscheduled_attempt}/execute")
        # Should return 400 or 404
        self.assertIn(res.status_code, [400, 404])

    def test_full_execution_flow(self):
        attempt_id = self.third_attempt_id
        # 1. Analyze
        analyze_res = self.client.post(f"/api/recovery/{attempt_id}/analyze")
        self.assertEqual(analyze_res.status_code, 200)
        analysis = analyze_res.json()
        
        # 2. Schedule via Agent with customer consent
        agent_res = self.client.post(f"/api/agent/{attempt_id}/message", json={"message": "Yes, schedule retry"})
        self.assertEqual(agent_res.status_code, 200)
        
        # 3. Check status
        status_res = self.client.get(f"/api/recovery/{attempt_id}/status")
        self.assertEqual(status_res.status_code, 200)
        
        # 4. If scheduled, execute via execution endpoint
        if status_res.json()["status"] == "SCHEDULED":
            exec_res = self.client.post(f"/api/recovery/{attempt_id}/execute")
            self.assertEqual(exec_res.status_code, 200)
            exec_data = exec_res.json()
            self.assertIn(exec_data["result"], ["SUCCESS", "FAILURE"])
            self.assertEqual(exec_data["attempt_id"], attempt_id)

if __name__ == '__main__':
    unittest.main()
