# Decision / Policy Engine Documentation

## 1. Purpose
The Decision Engine is a deterministic boundary layer between the predictive ML models and the future LLM conversational agent. It converts mathematical probabilities and contextual metadata into a single, constrained, and auditable action directive. It ensures that the LLM agent cannot hallucinate financial policies, bypass consent checks, or override technical constraints.

## 2. Inputs
The engine consumes a structured `DecisionInput` containing:
- `attempt_id`: The ID of the failed mandate attempt.
- `recovery_probability`: The mathematical float output from the Recovery Prediction ML model.
- `recommended_retry_date`: The optimized date candidate from the Prediction Engine.
- `failure_reason`: Extracted from the transaction/bank failure code (e.g., INSUFFICIENT_BALANCE, TECHNICAL_FAILURE).
- `mandate_status`: Current status of the mandate itself (e.g., ACTIVE, REVOKED).
- `current_attempt_number`: The retry loop index.
- `previous_failed_attempts`: Historical context.

## 3. Available Decisions & Consent Boundary
The Policy Engine maps the input to exactly one of the following directives, while statically determining if customer consent is required to execute it:

| Decision Directive | Explanation | Requires Consent? |
|---|---|---|
| `REAUTHORIZE_MANDATE` | Mandate is revoked/invalid at the bank level. Customer must completely re-enroll. | `True` |
| `RETRY_NOW` | Failure is purely a bank API timeout/technical glitch. Immediate automatic retry. | `True` |
| `RESCHEDULE` | Strong probability of future funds exists. Agent should negotiate this date. | `True` |
| `WAIT_FOR_BETTER_WINDOW`| Some probability exists, but not enough to commit to a date yet. | `False` |
| `DO_NOT_RETRY` | Exhausted retry limits or zero probability of recovery (e.g., job loss). Stop automatic system. | `False` |
| `ALTERNATIVE_PAYMENT` | Fallback option (e.g., sending a payment link instead of an AutoPay ping). | `True` |

*(Note: While `RETRY_NOW` technically could be done without consent if T&Cs permit, the MVP strictly enforces `requires_customer_consent=True` to adhere to the safety boundaries defined in the PRD unless a future specific legal policy is added).*

## 4. Policy Rules & Priority Queue
The engine executes rules in a strict, short-circuiting priority queue. If a high-priority rule triggers, all subsequent rules are ignored. This guarantees deterministic behavior for conflicting states.

1. **Invalid/Revoked Mandate Rule:** If `mandate_status != ACTIVE` $\rightarrow$ `REAUTHORIZE_MANDATE`. *(Overrides everything).*
2. **Retry Loop Protection Rule:** If `current_attempt_number > max_retries` $\rightarrow$ `DO_NOT_RETRY`. *(Prevents infinite loops even if probability is high).*
3. **Technical Failure Rule:** If `failure_reason == TECHNICAL_FAILURE` $\rightarrow$ `RETRY_NOW`. *(Bypasses the ML probability model entirely).*
4. **High Probability Rule:** If `probability >= high_recovery_threshold` $\rightarrow$ `RESCHEDULE` to the ML-predicted optimal date.
5. **Low Probability Rule:** If `probability < low_recovery_threshold` $\rightarrow$ `DO_NOT_RETRY`.
6. **Uncertainty Fallback:** If the probability falls into the grey zone between thresholds $\rightarrow$ `WAIT_FOR_BETTER_WINDOW`.

## 5. Threshold Configuration
The behavior is fully configurable via the `PolicyConfig` model without changing code:
- `high_recovery_threshold`: Defaults to `0.70` (70%).
- `low_recovery_threshold`: Defaults to `0.40` (40%).
- `max_retries`: Defaults to `3`.

## 6. Reason Codes
Every decision outputs a machine-readable array of reason codes for analytics and auditing:
- `MANDATE_REVOKED`
- `RETRY_LIMIT_REACHED`
- `TECHNICAL_FAILURE`
- `HIGH_RECOVERY_PROBABILITY`
- `LOW_RECOVERY_PROBABILITY`
- `EXPECTED_BETTER_WINDOW`
- `VALID_RETRY_WINDOW`

## 7. How the Future LangGraph Agent Will Consume This
The upcoming Agent architecture will call `DecisionEngine.evaluate()`. It will receive the `DecisionOutput`.
- If `requires_customer_consent == False` (e.g., `DO_NOT_RETRY`), the agent process simply stops and logs the failure to the database without messaging the user.
- If `requires_customer_consent == True`, the Agent takes the `decision` (e.g., `RESCHEDULE`) and the `recommended_retry_date`, formats a natural language negotiation strategy, and messages the user via chat. The agent's LLM prompt will be strictly bounded by the directive chosen here.
