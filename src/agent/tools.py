from typing import Dict, Any
from langchain_core.tools import tool
from src.decision.decision_models import DecisionOutput

class ToolException(Exception):
    """Exception raised when a tool fails its deterministic boundary checks."""
    pass

@tool
def schedule_retry(attempt_id: str, agreed_date: str, consent_granted: bool, decision_context: dict) -> str:
    """
    Schedules a retry for the mandate attempt. 
    MUST ONLY BE CALLED if consent was granted and the Decision Engine authorized the specific date.
    
    Args:
        attempt_id: The ID of the failed attempt.
        agreed_date: The date agreed upon with the customer (YYYY-MM-DD format).
        consent_granted: Boolean flag indicating if the customer explicitly said 'yes'.
        decision_context: The dictionary representation of the DecisionOutput.
    """
    
    if not consent_granted:
        raise ToolException("Cannot schedule retry: Customer consent was not granted.")
        
    decision = decision_context.get("decision")
    authorized_date = decision_context.get("recommended_retry_date")
    
    if decision not in ["RESCHEDULE", "RETRY_NOW"]:
        raise ToolException(f"Cannot schedule retry: Decision Engine directive is {decision}, not authorized for retry.")
        
    if decision == "RESCHEDULE" and agreed_date != authorized_date:
        raise ToolException(f"Cannot schedule retry: Agreed date {agreed_date} does not match authorized date {authorized_date}.")
        
    # In the MVP, we instantiate the services here.
    # In production, they would be injected dependencies.
    from src.consent.consent_service import ConsentService
    from src.simulator.outcome_service import OutcomeService
    from src.simulator.mandate_scheduler import MandateScheduler, SchedulerException
    
    consent_service = ConsentService()
    outcome_service = OutcomeService()
    scheduler = MandateScheduler(consent_service, outcome_service)
    
    try:
        # We need customer_id. It's stored in decision_context state logically or we pass it down.
        # For prototype simplicity we mock a customer ID if not provided.
        customer_id = decision_context.get("customer_id") or "CUST0001" 
        
        result = scheduler.schedule_retry(
            attempt_id=attempt_id,
            customer_id=customer_id,
            agreed_date=agreed_date,
            decision_context=decision_context,
            action_consent_granted=consent_granted
        )
        return result
    except SchedulerException as e:
        raise ToolException(str(e))

@tool
def trigger_fallback(attempt_id: str, fallback_type: str, decision_context: dict) -> str:
    """
    Triggers a manual fallback action (like sending a payment link) when automatic retries are aborted.
    
    Args:
        attempt_id: The ID of the failed attempt.
        fallback_type: The type of fallback (e.g., "PAYMENT_LINK", "MANUAL_TRANSFER").
        decision_context: The dictionary representation of the DecisionOutput.
    """
    
    decision = decision_context.get("decision")
    if decision in ["RESCHEDULE", "RETRY_NOW"]:
        raise ToolException("Cannot trigger fallback: A retry is currently authorized.")
        
    return f"Successfully triggered fallback {fallback_type} for {attempt_id}."
