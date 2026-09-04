# Data Contract: Mandate Recovery Agent

This document formally defines the data contract that all future components, Machine Learning models, and Agents must follow for the Mandate Recovery MVP.

## 1. Canonical Dataset
> **"The canonical CSVs were the given hackathon dataset; we treated them as ground truth and audited them for leakage — full audit in docs/DATA_AUDIT.md."**

The current 6 CSV files located in the `data/` directory constitute the **canonical dataset** for the MVP. They must not be modified, regenerated, or overwritten. For provenance and leakage audit details, refer to [docs/DATA_PROVENANCE.md](DATA_PROVENANCE.md) and [docs/DATA_AUDIT.md](DATA_AUDIT.md).

The 6 canonical datasets are:
1. `customers.csv`
2. `transactions.csv`
3. `mandates.csv`
4. `mandate_attempts.csv`
5. `consents.csv`
6. `recovery_actions.csv`

## 2. Entity Model
The relational structure of the ecosystem is defined as follows:
- **Customers**: The root entity.
- **Customers** grant **Consents** (1:N) allowing access to their data.
- **Customers** register **Mandates** (1:N) for recurring payments.
- **Customers** perform **Transactions** (1:N) over time.
- **Mandates** trigger **Mandate Attempts** (1:N) on their scheduled dates.
- **Mandate Attempts** lead to **Recovery Actions** (1:1 or 1:N), which track historical interventions.
- **Customers** are directly tied to their respective **Mandate Attempts** and **Recovery Actions**.

## 3. Dataset-Level Contract

### `customers.csv`
- **Purpose**: Demographic and behavioral profile of the customer.
- **Primary Key**: `customer_id`
- **Foreign Keys**: None
- **Important Fields**: `behavior_type`, `scenario_tag`, `avg_monthly_income`, `avg_balance_low`, `avg_balance_high`, `income_day_of_month`
- **Categorical Values**: 
  - `behavior_type`: EARLY_MONTH_SALARIED, FREELANCER_IRREGULAR, HIGH_SPENDER, MID_MONTH_SALARIED, RECOVERABLE_PATTERN, HIGH_MANDATE_RATIO, BUSINESS_OWNER
  - `scenario_tag`: GOLDEN_HIGH_MANDATE_RATIO, GOLDEN_SALARY_TIMING_MISMATCH, GOLDEN_MANDATE_REVOKED, GOLDEN_HIGH_SPENDER, GOLDEN_EARLY_MONTH_SALARY, GOLDEN_IRREGULAR_INCOME
- **Missing-Value Semantics**: `scenario_tag` is empty for standard users without a specific golden path scenario. `income_day_of_month` is empty for users with irregular incomes.
- **Usage**: Prediction (features), Agent decisions, Demo display.

### `transactions.csv`
- **Purpose**: Time-series financial transaction history.
- **Primary Key**: `transaction_id`
- **Foreign Keys**: `customer_id`
- **Important Fields**: `date`, `type`, `category`, `amount`, `balance_after`
- **Categorical Values**: 
  - `type`: debit, credit
  - `category`: rent, salary, p2p, groceries, gig_payout, transfer_in, utility_bill, entertainment
- **Missing-Value Semantics**: None.
- **Usage**: Prediction (historical features), Agent decisions, Demo display.

### `mandates.csv`
- **Purpose**: Registered UPI AutoPay mandates and their status.
- **Primary Key**: `mandate_id`
- **Foreign Keys**: `customer_id`
- **Important Fields**: `merchant_name`, `amount`, `frequency`, `due_day_of_month`, `status`
- **Categorical Values**: 
  - `status`: active, paused, revoked
  - `frequency`: monthly
- **Missing-Value Semantics**: None.
- **Usage**: Prediction (features), Agent decisions, Demo display.

### `mandate_attempts.csv`
- **Purpose**: Log of mandate execution attempts, including failures and ground-truth recovery labels.
- **Primary Key**: `attempt_id`
- **Foreign Keys**: `mandate_id`, `customer_id`
- **Important Fields**: `scheduled_date`, `attempt_date`, `status`, `failure_reason`, `ground_truth_retry_date`, `ground_truth_recoverable`
- **Categorical Values**: 
  - `status`: SUCCESS, FAILED
  - `failure_reason`: TECHNICAL_FAILURE, INSUFFICIENT_BALANCE, ACCOUNT_ISSUE, BANK_DECLINED, MANDATE_REVOKED
  - `ground_truth_recoverable`: TRUE, FALSE
- **Missing-Value Semantics**: `failure_reason` is empty for SUCCESS. `ground_truth_retry_date` and `ground_truth_recoverable` are empty for successful attempts or unrecoverable edge cases.
- **Usage**: Evaluation (Labels), Demo display. Features (up to the exact attempt date only).

### `consents.csv`
- **Purpose**: Manages user consent for data access (Account Aggregator framework simulation).
- **Primary Key**: `consent_id`
- **Foreign Keys**: `customer_id`
- **Important Fields**: `consent_status`, `data_scope`, `expiry_date`
- **Categorical Values**: 
  - `consent_status`: ACTIVE, EXPIRED, REVOKED
  - `data_scope`: TRANSACTIONS
- **Missing-Value Semantics**: None.
- **Usage**: Agent decisions (Permission boundary), Demo display.

### `recovery_actions.csv`
- **Purpose**: Historical records of previous recovery decisions, predictions, and actual outcomes.
- **Primary Key**: `recovery_id`
- **Foreign Keys**: `attempt_id`, `customer_id`
- **Important Fields**: `predicted_retry_date`, `recovery_probability`, `recommended_action`, `actual_retry_result`
- **Categorical Values**: 
  - `recommended_action`: DO_NOT_RETRY, RETRY_NOW, RESCHEDULE, ALTERNATIVE_PAYMENT
  - `customer_response`: DECLINED, ACCEPTED, NO_RESPONSE, NOT_REQUIRED
  - `actual_retry_result`: SUCCESS, FAILED, NOT_ATTEMPTED
- **Missing-Value Semantics**: `predicted_retry_date` and `scheduled_retry_date` may be empty depending on the action taken.
- **Usage**: Evaluation (historical decisions), Demo display.

---

## 4. Prediction-Time Data Contract
To prevent cheating, ML models and Agents are strictly bound to the exact moment a mandate fails. 

**Allowed Information (Available at Prediction Time):**
- Customer profile information.
- Historical transactions strictly occurring **before or on** the `attempt_date`.
- The customer's balance at the time of the attempt (`balance_at_attempt`).
- Mandate details (amount, merchant).
- Failure reason of the current attempt.
- Previous attempt history (prior `attempt_date`s).
- Valid consent status and scope.

**Prohibited Information:**
- Any future transaction occurring after the `attempt_date`.
- Future actions taken by the customer or the system.

---

## 5. ML Feature vs Label Contract

### Features ($X$)
Features must strictly be derived from information available before or during the failed attempt (see Section 4).

### Labels ($y$)
The system predicts two primary targets:
- `ground_truth_recoverable` (Binary Classification)
- `ground_truth_retry_date` (Regression / Time-to-event)

### 🚫 Strictly Prohibited Features
The following fields **MUST NOT** be used as input features ($X$) under any circumstances:

1. **`ground_truth_recoverable`**: This is the exact answer. Using it guarantees artificial 100% accuracy (Direct Target Leakage).
2. **`ground_truth_retry_date`**: This tells the model exactly when the user will have funds. Using it circumvents the need to learn financial patterns (Direct Target Leakage).
3. **`recovery_probability`**: This is a prediction from a previous system. Using it causes the model to mimic the old system's biases rather than learning from raw data (Previous-Model Output Leakage).
4. **`predicted_retry_date`**: Same as above (Previous-Model Output Leakage).
5. **`recommended_action`**: This is a deterministic output of a previous heuristics engine. The model must learn the correct action independently.

---

## 6. Recovery Actions Contract
The `recovery_actions.csv` file represents existing/reference recovery decisions and their outcomes.
- **DO NOT** treat `recovery_probability` or `recommended_action` as ground truth labels. They are historical estimates.
- `actual_retry_result` **may** be used for evaluation of recovery outcomes (to see if the historical system's action succeeded or failed), but it must not be used as a feature to predict initial recovery probability.

---

## 7. Consent Contract
The `consents.csv` file acts as a strict **permission boundary**.

- **Values**: `ACTIVE`, `EXPIRED`, `REVOKED`.
- **Scope**: `TRANSACTIONS`.
- **Rule**: Customer-level financial-data operations (e.g., aggregating past transactions, viewing income, ML inference on history) **MUST** respect valid consent. 
- If a customer's consent is `EXPIRED` or `REVOKED`, the agent and application logic must immediately block processing of their transaction history.

---

## 8. Data Leakage Rules
All data processing must explicitly prevent:
- **Future Transaction Leakage**: Joining transactions where `transaction.date > mandate_attempts.attempt_date`.
- **Ground-Truth Leakage**: Including `ground_truth_*` fields in the feature vector.
- **Previous-Model-Output Leakage**: Including predictions (`predicted_retry_date`, `recovery_probability`, `recommended_action`) from `recovery_actions.csv` in training.
- **Post-Recovery Information Leakage**: Using `actual_retry_result` or `customer_response` to predict the initial probability of recovery.

---

## 9. Data Join Rules
All data joins must utilize the primary and foreign keys securely. Safe joins include:
- `customers` ⟷ `mandates` on `customer_id`
- `mandates` ⟷ `mandate_attempts` on `mandate_id`
- `customers` ⟷ `transactions` on `customer_id` *(Crucial: must filter by `transaction.date <= attempt.date`)*
- `customers` ⟷ `consents` on `customer_id`
- `mandate_attempts` ⟷ `recovery_actions` on `attempt_id`

---

## 10. Data Quality Rules
Pipelines ingesting this data must validate against the following rules:
- **Missing Required IDs**: Primary Keys (e.g., `customer_id`) and Foreign Keys must not be null.
- **Invalid Foreign Keys**: Any Foreign Key must exist in its parent table.
- **Duplicate Primary Keys**: No exact duplicates allowed for Primary Keys.
- **Invalid Dates**: Dates must follow standard ISO formats (`YYYY-MM-DD`). `attempt_date` must be $\ge$ `scheduled_date`.
- **Invalid Statuses**: Categorical statuses must strictly match the allowed lists defined in Section 3.
- **Impossible Financial Values**: `amount`, `balance_after`, `avg_monthly_income`, and `avg_balance_low` must be $\ge 0$.

---

## 11. Future Reproducibility Note
The current CSV dataset is treated as the **canonical source of truth** for the MVP. 

The existing `generate_synthetic_data.py` represents an older/incomplete generation pipeline. To avoid blocking MVP development, the generator will not be rewritten now. It will be reconstructed at a later date to align with this Data Contract and ensure full reproducibility.
