from typing import TypedDict, List, Optional
from src.decision.decision_models import DecisionOutput

class AgentState(TypedDict):
    """The typed state object representing the agent's memory and strict context boundaries."""
    attempt_id: str
    customer_id: str
    mandate_id: str
    
    # Authoritative Context
    decision_context: DecisionOutput
    
    # Conversational Memory
    messages: List[str] # List of conversation strings (User/Agent)
    
    # Execution Flags
    consent_granted: bool
    action_status: str # e.g. "PENDING", "COMPLETED", "FAILED", "CANCELLED"
    fallback_reason: Optional[str]
