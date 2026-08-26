from .decision_models import PolicyConfig, DecisionInput, DecisionOutput

class DecisionEngine:
    def __init__(self, config: PolicyConfig = None):
        self.config = config or PolicyConfig()

    def evaluate(self, context: DecisionInput) -> DecisionOutput:
        """
        Evaluates the input context against the configured policy rules strictly in priority order.
        """
        
        # Rule 1: Invalid/Revoked Mandate
        # If the mandate is revoked or paused, it's impossible to retry automatically.
        if context.mandate_status.upper() != 'ACTIVE':
            return DecisionOutput(
                attempt_id=context.attempt_id,
                decision="REAUTHORIZE_MANDATE",
                recommended_retry_date=None,
                recovery_probability=context.recovery_probability,
                reason_codes=["MANDATE_REVOKED"],
                explanation="The mandate is no longer active and cannot be retried.",
                requires_customer_consent=True
            )
            
        # Rule 2: Retry Loop Protection
        # If we have reached the configured limit of attempts without success.
        if context.current_attempt_number > self.config.max_retries:
            return DecisionOutput(
                attempt_id=context.attempt_id,
                decision="DO_NOT_RETRY",
                recommended_retry_date=None,
                recovery_probability=context.recovery_probability,
                reason_codes=["RETRY_LIMIT_REACHED"],
                explanation=f"Maximum retry limit ({self.config.max_retries}) exceeded.",
                requires_customer_consent=False
            )
            
        # Rule 3: Technical Failure
        # If the failure is a known technical glitch (e.g., NPCI timeout), retry immediately.
        # It does not depend on financial probability.
        if context.failure_reason.upper() == 'TECHNICAL_FAILURE':
            return DecisionOutput(
                attempt_id=context.attempt_id,
                decision="RETRY_NOW",
                recommended_retry_date=None,
                recovery_probability=context.recovery_probability, # Keep original context
                reason_codes=["TECHNICAL_FAILURE"],
                explanation="The failure was due to a technical error. Retrying immediately.",
                requires_customer_consent=True
            )
            
        # Rule 4: High Recovery Probability
        # If the ML model is highly confident in the future date, reschedule it.
        if context.recovery_probability >= self.config.high_recovery_threshold:
            return DecisionOutput(
                attempt_id=context.attempt_id,
                decision="RESCHEDULE",
                recommended_retry_date=context.recommended_retry_date,
                recovery_probability=context.recovery_probability,
                reason_codes=["HIGH_RECOVERY_PROBABILITY", "VALID_RETRY_WINDOW"],
                explanation=f"Strong probability of recovery predicted for {context.recommended_retry_date}.",
                requires_customer_consent=True
            )
            
        # Rule 5: Low Recovery Probability
        # If the ML model predicts extremely low chances, do not retry and save processing costs.
        if context.recovery_probability < self.config.low_recovery_threshold:
            return DecisionOutput(
                attempt_id=context.attempt_id,
                decision="DO_NOT_RETRY",
                recommended_retry_date=None,
                recovery_probability=context.recovery_probability,
                reason_codes=["LOW_RECOVERY_PROBABILITY"],
                explanation="Financial patterns indicate low chance of recovery. Pausing automatic retries.",
                requires_customer_consent=False
            )
            
        # Rule 6: Uncertain / Wait
        # Probability is between low and high threshold. Better to wait for a stronger signal
        # or have the agent engage without committing to a hard automatic retry.
        return DecisionOutput(
            attempt_id=context.attempt_id,
            decision="WAIT_FOR_BETTER_WINDOW",
            recommended_retry_date=context.recommended_retry_date,
            recovery_probability=context.recovery_probability,
            reason_codes=["EXPECTED_BETTER_WINDOW"],
            explanation="Recovery probability is marginal. Waiting for a better financial window.",
            requires_customer_consent=False
        )
