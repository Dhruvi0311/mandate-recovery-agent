from src.agent.state import AgentState

class MockLLM:
    """
    A deterministic LLM used for adversarial testing and live rogue-agent simulations.
    Emits specific valid or malicious tool calls to verify non-bypassable tool boundary rules.
    """
    def __init__(self, response_type="schedule_success"):
        self.response_type = response_type
        
    def invoke(self, state: AgentState):
        if self.response_type == "schedule_success":
            return {
                "tool_calls": [{
                    "name": "schedule_retry",
                    "args": {"agreed_date": "2026-07-01"}
                }]
            }
        elif self.response_type == "schedule_hallucinated_date":
            return {
                "tool_calls": [{
                    "name": "schedule_retry",
                    "args": {"agreed_date": "2099-01-01"} # Malicious/hallucinated date
                }]
            }
        elif self.response_type == "text_fallback":
            return {
                "content": "Since you said no, I will not schedule the retry."
            }
        elif self.response_type == "unauthorized_retry_on_do_not_retry":
            return {
                "tool_calls": [{
                    "name": "schedule_retry",
                    "args": {"agreed_date": "2026-07-01"}
                }]
            }
        return {
            "content": "I am unable to process this request."
        }
