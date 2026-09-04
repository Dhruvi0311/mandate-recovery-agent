import unittest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.dependencies import get_db_path
import sqlite3

class TestAgentConversationRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        conn = sqlite3.connect(get_db_path())
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM agent_conversations WHERE attempt_id IN ('ATMPT00005', 'ATMPT00006', 'ATMPT00010')")
            conn.commit()
        finally:
            conn.close()

    def test_initial_opening_message_count_is_exactly_one_for_scenario_a(self):
        """Regression test: GET /api/agent/ATMPT00005 returns exactly one initial agent greeting."""
        res = self.client.get("/api/agent/ATMPT00005")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Initial message count must be exactly 1
        self.assertEqual(len(data["messages"]), 1)
        self.assertTrue(data["messages"][0].startswith("Agent: "))
        self.assertIn("optimal funds on 2026-07-21", data["messages"][0])

        # Idempotency test: calling again must NOT duplicate the opening message
        res2 = self.client.get("/api/agent/ATMPT00005")
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(len(data2["messages"]), 1)
        self.assertEqual(data2["messages"][0], data["messages"][0])

    def test_initial_opening_message_count_is_exactly_one_for_scenario_b(self):
        """Regression test: GET /api/agent/ATMPT00006 returns exactly one initial agent greeting."""
        res = self.client.get("/api/agent/ATMPT00006")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Initial message count must be exactly 1
        self.assertEqual(len(data["messages"]), 1)
        self.assertTrue(data["messages"][0].startswith("Agent: "))
        self.assertIn("DO_NOT_RETRY", data["messages"][0])

        # Idempotency check
        res2 = self.client.get("/api/agent/ATMPT00006")
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(len(data2["messages"]), 1)

    def test_subsequent_conversation_appends_single_customer_and_agent_response(self):
        """Ensures subsequent conversation preserves single-message turns without duplication."""
        # Use an isolated attempt
        attempt_id = "ATMPT00010"
        init_res = self.client.get(f"/api/agent/{attempt_id}")
        self.assertEqual(init_res.status_code, 200)
        init_data = init_res.json()
        self.assertEqual(len(init_data["messages"]), 1)
        self.assertTrue(init_data["messages"][0].startswith("Agent: "))

        # Customer sends a question
        turn_res = self.client.post(f"/api/agent/{attempt_id}/message", json={"message": "Why did my mandate fail?"})
        self.assertEqual(turn_res.status_code, 200)
        turn_data = turn_res.json()
        
        # Should now have: initial greeting + customer question + agent response
        self.assertGreaterEqual(len(turn_data["messages"]), 2)
        customer_msgs = [m for m in turn_data["messages"] if m.startswith("Customer: ")]
        self.assertEqual(len(customer_msgs), 1)
        self.assertEqual(customer_msgs[0], "Customer: Why did my mandate fail?")

    def test_consecutive_duplicate_messages_are_never_rendered_or_saved(self):
        """Ensures that consecutive duplicate agent or tool messages are sanitized."""
        attempt_id = "ATMPT00005"
        # 1. Initialize
        res = self.client.get(f"/api/agent/{attempt_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["messages"]), 1)

        # 2. Consent to schedule retry
        res2 = self.client.post(f"/api/agent/{attempt_id}/message", json={"message": "Yes, please schedule it"})
        self.assertEqual(res2.status_code, 200)
        msgs2 = res2.json()["messages"]
        for i in range(1, len(msgs2)):
            self.assertNotEqual(msgs2[i], msgs2[i - 1], f"Consecutive duplicate message found at index {i}: {msgs2[i]}")

        # 3. Simulate existing conversation containing consecutive duplicate injected into DB
        conn = sqlite3.connect(get_db_path())
        try:
            cursor = conn.cursor()
            import json
            duplicated = [
                msgs2[0],
                msgs2[0], # duplicate opening
                "Customer: Yes, please schedule it",
                "Tool schedule_retry success: test",
                "Tool schedule_retry success: test" # duplicate tool
            ]
            cursor.execute("UPDATE agent_conversations SET messages_json = ? WHERE attempt_id = ?", (json.dumps(duplicated), attempt_id))
            conn.commit()
        finally:
            conn.close()

        # 4. Fetching conversation must clean consecutive duplicates
        fetch_res = self.client.get(f"/api/agent/{attempt_id}")
        self.assertEqual(fetch_res.status_code, 200)
        cleaned_msgs = fetch_res.json()["messages"]
        for i in range(1, len(cleaned_msgs)):
            self.assertNotEqual(cleaned_msgs[i], cleaned_msgs[i - 1], f"Consecutive duplicate still present: {cleaned_msgs[i]}")
        self.assertEqual(len(cleaned_msgs), 3)

if __name__ == "__main__":
    unittest.main()
