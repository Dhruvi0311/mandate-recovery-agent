from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class PolicyConfig:
    """Configurable thresholds for the Decision Engine."""
    high_recovery_threshold: float = 0.70
    low_recovery_threshold: float = 0.40
    max_retries: int = 3

@dataclass
class DecisionInput:
    """The required context payload containing predictions and mandate state."""
    attempt_id: str
    recovery_probability: float
    recommended_retry_date: str
    failure_reason: str
    mandate_status: str
    current_attempt_number: int
    previous_failed_attempts: int

@dataclass
class DecisionOutput:
    """The structured response containing the deterministic decision."""
    attempt_id: str
    decision: str
    recommended_retry_date: Optional[str]
    recovery_probability: float
    reason_codes: List[str]
    explanation: str
    requires_customer_consent: bool
