import unittest
from src.agent.state import AgentState
from src.agent.graph import build_graph
from src.decision.decision_models import DecisionOutput
from src.agent.mock_llm import MockLLM

class TestAgentGraph(unittest.TestCase):

    def setUp(self):
        from unittest.mock import patch
        self.patcher1 = patch('src.consent.consent_service.ConsentService.validate_data_consent')
        self.mock_validate = self.patcher1.start()
        self.mock_validate.return_value = {"valid": True, "status": "ACTIVE", "reason": "MOCK"}
        
        self.patcher2 = patch('src.simulator.outcome_service.OutcomeService.update_state')
        self.patcher2.start()

        self.base_decision = DecisionOutput(
            attempt_id="ATT001",
            decision="RESCHEDULE",
            recommended_retry_date="2026-07-01",
            recovery_probability=0.85,
            reason_codes=["HIGH_RECOVERY_PROBABILITY"],
            explanation="Test reschedule",
            requires_customer_consent=True
        )
        
        self.base_state = {
            "attempt_id": "ATT001",
            "customer_id": "CUST001",
            "mandate_id": "MAND001",
            "decision_context": self.base_decision,
            "messages": [],
            "consent_granted": False,
            "action_status": "PENDING",
            "fallback_reason": None
        }

    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()

    def test_reschedule_happy_path_with_consent(self):
        """LLM schedules successfully when consent is given and date matches."""
        llm = MockLLM(response_type="schedule_success")
        graph = build_graph(llm)
        
        state = dict(self.base_state)
        state["messages"] = ["Customer: Yes, please schedule it."] # Triggers True consent
        
        final_state = graph.invoke(state)
        
        self.assertEqual(final_state["action_status"], "COMPLETED")
        self.assertTrue(final_state["consent_granted"])
        self.assertIn("Successfully scheduled retry", final_state["messages"][-1])

    def test_schedule_tool_rejected_without_consent(self):
        """Tool explicitly rejects if LLM tries to call it when customer said No."""
        llm = MockLLM(response_type="schedule_success")
        graph = build_graph(llm)
        
        state = dict(self.base_state)
        state["messages"] = ["Customer: No, do not schedule."] # Triggers False consent
        
        final_state = graph.invoke(state)
        
        # Action MUST fail because the tool rejected the lack of consent
        self.assertEqual(final_state["action_status"], "FAILED")
        self.assertFalse(final_state["consent_granted"])
        self.assertIn("Tool execution rejected: Cannot schedule retry: Customer consent was not granted", final_state["messages"][-1])

    def test_schedule_tool_rejected_on_hallucinated_date(self):
        """Tool explicitly rejects if LLM tries to invent a date different from DecisionEngine."""
        llm = MockLLM(response_type="schedule_hallucinated_date")
        graph = build_graph(llm)
        
        state = dict(self.base_state)
        state["messages"] = ["Customer: Yes"] # Consent given, but LLM is hallucinating
        
        final_state = graph.invoke(state)
        
        self.assertEqual(final_state["action_status"], "FAILED")
        self.assertIn("Tool execution rejected: Cannot schedule retry: Agreed date 2099-01-01 does not match authorized date 2026-07-01.", final_state["messages"][-1])

    def test_do_not_retry_blocks_schedule_tool(self):
        """If DecisionEngine says DO_NOT_RETRY, the tool will reject schedule attempts."""
        llm = MockLLM(response_type="schedule_success") # Rogue LLM trying to schedule anyway
        graph = build_graph(llm)
        
        state = dict(self.base_state)
        state["decision_context"].decision = "DO_NOT_RETRY"
        state["messages"] = ["Customer: Yes please retry anyway"] # Customer tries to force it
        
        final_state = graph.invoke(state)
        
        self.assertEqual(final_state["action_status"], "FAILED")
        self.assertIn("Tool execution rejected: Cannot schedule retry: Decision Engine directive is DO_NOT_RETRY", final_state["messages"][-1])

if __name__ == '__main__':
    unittest.main()
