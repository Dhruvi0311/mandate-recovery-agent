import unittest
from src.decision.decision_models import PolicyConfig, DecisionInput
from src.decision.policy_engine import DecisionEngine

class TestPolicyEngine(unittest.TestCase):

    def setUp(self):
        self.config = PolicyConfig(high_recovery_threshold=0.75, low_recovery_threshold=0.30, max_retries=2)
        self.engine = DecisionEngine(config=self.config)

    def _base_input(self) -> dict:
        return {
            "attempt_id": "TEST_001",
            "recovery_probability": 0.80,
            "recommended_retry_date": "2026-07-01",
            "failure_reason": "INSUFFICIENT_BALANCE",
            "mandate_status": "ACTIVE",
            "current_attempt_number": 1,
            "previous_failed_attempts": 0
        }

    def test_revoked_mandate_priority(self):
        """Rule 1 overrides high probability and returns REAUTHORIZE_MANDATE."""
        data = self._base_input()
        data["mandate_status"] = "REVOKED"
        data["recovery_probability"] = 0.99  # Normally high enough to reschedule
        
        inp = DecisionInput(**data)
        out = self.engine.evaluate(inp)
        
        self.assertEqual(out.decision, "REAUTHORIZE_MANDATE")
        self.assertIn("MANDATE_REVOKED", out.reason_codes)
        self.assertTrue(out.requires_customer_consent)

    def test_retry_loop_protection(self):
        """Rule 2 overrides high probability if limits are exceeded."""
        data = self._base_input()
        data["current_attempt_number"] = 3 # max is 2
        data["recovery_probability"] = 0.90
        
        inp = DecisionInput(**data)
        out = self.engine.evaluate(inp)
        
        self.assertEqual(out.decision, "DO_NOT_RETRY")
        self.assertIn("RETRY_LIMIT_REACHED", out.reason_codes)
        self.assertFalse(out.requires_customer_consent)

    def test_technical_failure(self):
        """Rule 3 forces RETRY_NOW even if probability is low."""
        data = self._base_input()
        data["failure_reason"] = "TECHNICAL_FAILURE"
        data["recovery_probability"] = 0.10 # Extremely low
        
        inp = DecisionInput(**data)
        out = self.engine.evaluate(inp)
        
        self.assertEqual(out.decision, "RETRY_NOW")
        self.assertIn("TECHNICAL_FAILURE", out.reason_codes)

    def test_high_recovery_probability(self):
        """Rule 4 reschedules when prob >= high threshold."""
        data = self._base_input()
        data["recovery_probability"] = 0.75 # exactly hits threshold
        
        inp = DecisionInput(**data)
        out = self.engine.evaluate(inp)
        
        self.assertEqual(out.decision, "RESCHEDULE")
        self.assertIn("HIGH_RECOVERY_PROBABILITY", out.reason_codes)
        self.assertTrue(out.requires_customer_consent)

    def test_low_recovery_probability(self):
        """Rule 5 stops retries when prob < low threshold."""
        data = self._base_input()
        data["recovery_probability"] = 0.29 
        
        inp = DecisionInput(**data)
        out = self.engine.evaluate(inp)
        
        self.assertEqual(out.decision, "DO_NOT_RETRY")
        self.assertIn("LOW_RECOVERY_PROBABILITY", out.reason_codes)
        self.assertFalse(out.requires_customer_consent)

    def test_uncertain_wait_for_better_window(self):
        """Rule 6 waits when prob is between thresholds."""
        data = self._base_input()
        data["recovery_probability"] = 0.50 # between 0.30 and 0.75
        
        inp = DecisionInput(**data)
        out = self.engine.evaluate(inp)
        
        self.assertEqual(out.decision, "WAIT_FOR_BETTER_WINDOW")
        self.assertIn("EXPECTED_BETTER_WINDOW", out.reason_codes)
        self.assertFalse(out.requires_customer_consent)

if __name__ == '__main__':
    unittest.main()
