# Product Requirements Document (PRD)

## 1. Product Overview
- **Product Name:** Mandate Recovery Agent
- **Description:** An intelligent, data-driven system that manages failed UPI AutoPay mandates by analyzing customer financial patterns to predict the optimal retry window, and utilizes an AI Agent to negotiate rescheduled payments with the customer.
- **Core Value Proposition:** Replaces naive, blind retry strategies with targeted, data-backed interventions to maximize recovered revenue, minimize bank bounce penalties for users, and reduce involuntary churn.

## 2. Problem Statement
When a recurring payment (UPI AutoPay mandate) fails, the standard industry approach is a blind "payment failed → retry later" loop. This naive strategy is highly flawed because it ignores the customer's actual financial reality, leading to repeated failures, stacked bank bounce penalties for the customer, and eventual service cancellation. 

To solve this, the recovery system must answer three core questions:
1. **Why did it fail?** (e.g., insufficient balance, technical error, revoked mandate)
2. **When is it likely to succeed?** (e.g., when does the user typically receive their salary or gig payout?)
3. **Should we retry at all?** (e.g., is the user permanently out of funds, making retries futile and harmful?)

## 3. Target Users
1. **Merchant / Merchant Operations:** Businesses relying on subscription or recurring revenue (e.g., OTT platforms, gyms, lenders).
2. **Customer / Mandate Holder:** End-users who have set up UPI AutoPay for their recurring obligations.

## 4. User Problems
- **Merchant:** Suffers from lost revenue, high involuntary churn due to payment failures, and the high operational cost of manually chasing customers for failed payments.
- **Customer:** Faces excessive bank bounce fees due to repeated blind retries when they simply don't have funds yet. Experiences annoyance and friction when badgered for payment on the wrong day (e.g., billing on the 1st, but salary arrives on the 5th).

## 5. Product Goals
- Accurately predict whether a failed mandate is recoverable based on historical transaction data.
- Accurately predict the optimal date to retry the mandate.
- Automate the recovery process via an AI agent that secures user consent for the new retry date.
- Avoid unnecessary retries for customers who lack the capacity to pay.

## 6. Non-Goals
This MVP is a technically credible hackathon proof-of-concept. It will **NOT**:
- Execute real UPI payments.
- Connect to real bank accounts or banking APIs.
- Use real Account Aggregator (AA) infrastructure.
- Modify real mandates.
- Make real financial transactions.
- Silently retry payments without customer consent.

*Note: The MVP relies exclusively on the synthetic AA-consented data and a simulated mandate execution environment defined in `DATA_CONTRACT.md`.*

## 7. Core Product Workflow
The complete lifecycle of a mandate recovery in the MVP:

1. **Failed Mandate** (A scheduled attempt fails)
2. **Failure Analysis** (Identify reason: e.g., insufficient funds)
3. **Financial Pattern Analysis** (Analyze AA-consented transactions)
4. **Recovery Probability** (ML predicts likelihood of future success)
5. **Optimal Retry Window** (ML predicts the specific date funds will be available)
6. **Retry / Don't-Retry Decision** (Policy engine decides the path)
7. **AI Recovery Agent** (Triggered if retry is viable)
8. **Customer Consent** (Agent interacts with user to agree on the new date)
9. **Smart Retry OR Alternative Recovery** (Execute the agreed plan or fallback)
10. **Simulated Outcome** (Evaluate against ground truth)

## 8. MVP Features
The MVP is strictly limited to the following 11 locked features:

1. **Intelligent Failure Detection**
   - **Purpose:** Ingest mandate attempts and identify failures.
   - **Input:** `mandate_attempts.csv`
   - **Output:** Flagged failed attempts ready for analysis.
   - **User Value:** Automates the start of the recovery pipeline.
2. **Failure Reason Analysis**
   - **Purpose:** Categorize why the mandate failed to route it correctly (e.g., technical vs. insufficient funds).
   - **Input:** Failure reason from attempt record.
   - **Output:** Categorized failure state.
   - **User Value:** Prevents harassing users for technical bank failures.
3. **Amount-Aware Recovery**
   - **Purpose:** Evaluate the specific shortfall.
   - **Input:** `amount_required`, `balance_at_attempt`.
   - **Output:** Delta required for success.
   - **User Value:** Contextualizes the severity of the failure.
4. **Financial Pattern Analysis**
   - **Purpose:** Extract features from the user's transaction history.
   - **Input:** `transactions.csv` (strictly prior to attempt date).
   - **Output:** Income cadence, average balances, spending velocity.
   - **User Value:** Forms the basis of empathetic, data-driven recovery.
5. **Dynamic Retry-Window Prediction**
   - **Purpose:** Predict the date/window with the highest estimated probability of successful recovery
   - **Input:** Financial features.
   - **Output:** Predicted Date.
   - **User Value:** Eliminates bounce penalties by retrying only when funds exist.
6. **Retry / Don't-Retry Decision Engine**
   - **Purpose:** Apply business logic to ML outputs.
   - **Input:** Predictions, consent status, mandate status.
   - **Output:** Final routing decision (Agent vs. Fallback).
   - **User Value:** Protects users with zero capacity to pay from endless retries.
7. **Recovery Probability Score**
   - **Purpose:** Quantify the likelihood of successful recovery.
   - **Input:** Financial features.
   - **Output:** Percentage score (0-100%).
   - **User Value:** Allows merchants to prioritize high-value/high-probability recoveries.
8. **AI Recovery Agent**
   - **Purpose:** Conversational interface to handle the recovery.
   - **Input:** Decision engine output, predicted date.
   - **Output:** Natural language interaction with the user.
   - **User Value:** Reduces operational overhead while maintaining a human-like, empathetic touch.
9. **Consent-Based Rescheduling**
   - **Purpose:** Negotiate and lock in the retry date with the user.
   - **Input:** User's chat response.
   - **Output:** Approved new scheduled date.
   - **User Value:** Empowers the user and complies with regulations.
10. **Smart Retry Execution**
    - **Purpose:** Simulate the execution of the mandate on the newly agreed date.
    - **Input:** Approved scheduled date.
    - **Output:** Simulated Success/Failure.
    - **User Value:** Completes the recovery loop.
11. **Fallback Recovery Path**
    - **Purpose:** Handle cases where retry is impossible.
    - **Input:** Low probability score or revoked mandate.
    - **Output:** Alternative recommendation (e.g., pause subscription, send manual payment link).
    - **User Value:** Preserves the customer relationship even when AutoPay fails.

## 9. User Stories
- **Merchant:** As a merchant operations manager, I want the system to automatically analyze failed mandates and predict if they are recoverable, so I don't waste money and customer goodwill on futile retries.
- **Customer:** As a customer, I want to be notified when my AutoPay fails due to low balance, and I want an intelligent assistant to offer rescheduling it to my payday, so I avoid paying ₹500 in bank bounce charges.

## 10. Functional Requirements
- The system must ingest the canonical CSV datasets securely.
- The system must filter transactions strictly by `date <= attempt_date` to prevent data leakage.
- The system must check `consents.csv` before analyzing any customer's transactions.
- The ML model must output a probability score and a recommended retry date.
- The Agent must be capable of presenting the recommendation to the user and parsing their acceptance/rejection.

## 11. AI / ML Requirements
To maintain system integrity, AI responsibilities are strictly separated:
- **Deterministic Calculations:** Standard code calculates current balances, historical averages, and checks consent status.
- **ML Prediction:** A dedicated ML model (or statistical heuristic for the MVP) predicts the probability of recovery and the target retry date based *only* on valid features.
- **Decision/Policy Engine:** Standard code maps the ML probability to a business action (The policy engine applies a configurable recovery threshold determined through evaluation).
- **LLM/Agent:** The LLM is responsible *only* for natural language communication and state negotiation. **The LLM must NOT independently calculate financial probabilities or bypass policy/consent controls.**

## 12. Consent Requirements
Customer financial-data processing must respect the data contract established in `DATA_CONTRACT.md`. 
- If `consents.csv` indicates a status of `EXPIRED` or `REVOKED` for a customer, the system is strictly prohibited from analyzing their `transactions.csv` data. The system must immediately route these cases to the Fallback Recovery Path.

## 13. Fallback Recovery Requirements
When the Recovery Probability Score is exceptionally low, or the mandate status is `revoked`, the system must bypass the Smart Retry path. It must instead trigger a fallback action, which includes recommending the merchant to pause the subscription, downgrade the user, or send a manual, non-automated payment link.

## 14. Success Metrics
- **Recovery Rate:** % of failed mandates successfully recovered.
- **Unnecessary Retries Avoided:** Number of doomed retries bypassed.
- **Model Performance (Classification):** AUC / F1 Score for `ground_truth_recoverable`.
- **Model Performance (Regression):** MAE (Mean Absolute Error) in days for `ground_truth_retry_date`.
- **Consent Violations:** Must be strictly **0**.

## 15. Demo Requirements
The MVP must be able to showcase at least two core scenarios end-to-end:
- **Scenario A (High-Probability Recoverable):** A user's mandate fails due to a salary timing mismatch. The system analyzes their history, accurately predicts their upcoming payday, triggers the AI Agent, secures user consent for the new date, and simulates a successful recovery.
- **Scenario B (Low-Probability Unrecoverable):** A user's mandate fails and their transaction history shows severe financial distress (e.g., A failed mandate with low predicted recovery probability based on the customer's historical financial pattern). The system determines a retry is futile, chooses NOT to retry, and recommends the merchant pause the service and offer an alternative payment plan.

## 16. Technical / Product Constraints
All data usage, joins, leakage prevention, and allowed features are strictly bound by the rules defined in `docs/DATA_CONTRACT.md`. 

## 17. Future Scope
The following items are explicitly out of scope for the MVP and reserved for future production releases:
- Real-time integration with NPCI / UPI AutoPay rails.
- Real-time integration with Account Aggregator (AA) gateways (e.g., Setu, Sahamati).
- Live webhooks for real-time transaction ingestion.
- Production-grade authentication and user management.
- Complex multi-agent negotiation strategies.
