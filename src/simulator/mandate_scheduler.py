from typing import Dict, Any
from src.consent.consent_service import ConsentService
from src.simulator.outcome_service import OutcomeService

class SchedulerException(Exception):
    pass

class MandateScheduler:
    def __init__(self, consent_service: ConsentService, outcome_service: OutcomeService):
        self.consent_service = consent_service
        self.outcome_service = outcome_service

    def schedule_retry(self, attempt_id: str, customer_id: str, agreed_date: str, 
                       decision_context: Dict[str, Any], action_consent_granted: bool) -> str:
        """
        Safely validates all boundaries and schedules the retry if authorized.
        """
        # 1. Check Action Consent (from the LLM conversation)
        if not action_consent_granted:
            self.outcome_service.update_state(attempt_id, customer_id, "ACTION_REJECTED", reason="No customer consent")
            raise SchedulerException("Customer did not consent to this action.")

        # 2. Check Data Consent (from Account Aggregator)
        data_consent = self.consent_service.validate_data_consent(customer_id, "TRANSACTIONS")
        if not data_consent["valid"]:
            self.outcome_service.update_state(attempt_id, customer_id, "ACTION_REJECTED", reason=f"Invalid AA consent: {data_consent['status']}")
            raise SchedulerException(f"Invalid Data Consent: {data_consent['reason']}")
            
        # 3. Check Decision Engine Authorization
        decision = decision_context.get("decision")
        if decision not in ["RESCHEDULE", "RETRY_NOW"]:
            self.outcome_service.update_state(attempt_id, customer_id, "ACTION_REJECTED", reason="Unauthorized decision directive")
            raise SchedulerException(f"Decision Engine blocked retry scheduling. Directive: {decision}")
            
        # 4. Check Date Matches (No Hallucination)
        authorized_date = decision_context.get("recommended_retry_date")
        if decision == "RESCHEDULE" and agreed_date != authorized_date:
            self.outcome_service.update_state(attempt_id, customer_id, "ACTION_REJECTED", reason="Date mismatch")
            raise SchedulerException(f"Agreed date {agreed_date} does not match authorized date {authorized_date}.")

        # 5. Success -> Write to SQLite
        self.outcome_service.update_state(
            attempt_id=attempt_id, 
            customer_id=customer_id, 
            status="SCHEDULED", 
            scheduled_date=agreed_date
        )
        return f"Successfully scheduled retry for {attempt_id} on {agreed_date}."
