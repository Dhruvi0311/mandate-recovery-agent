# Financial Feature Engineering Layer

This document details the features engineered for the Mandate Recovery ML Model and Decision Engine. All features strictly adhere to the time-travel prevention constraints defined in the Data Contract (only using data mathematically available at or before the `attempt_date`).

## Target & Leakage Prevention
The target variables are `ground_truth_recoverable` (classification) and `ground_truth_retry_date` (regression). 
**Prohibited Fields Excluded:** 
- `ground_truth_recoverable`, `ground_truth_retry_date`
- `recovery_probability`, `predicted_retry_date`, `recommended_action`, `actual_retry_result`, `customer_response`
- `scenario_tag` (Dropped completely due to target leakage encoding, e.g., `GOLDEN_MANDATE_REVOKED`).

---

## 1. Customer Features
Derived from `customers.csv`.

| Feature | Source Column | Logic | Why it predicts recovery |
|---|---|---|---|
| `behavior_type` | `behavior_type` | Categorical string directly from dataset. | Different persona behaviors (e.g., `HIGH_SPENDER` vs `EARLY_MONTH_SALARIED`) have distinct recovery probabilities. |
| `avg_monthly_income` | `avg_monthly_income` | Float cast. | Higher income generally correlates with higher capacity to recover from a temporary shortfall. |
| `income_day_of_month` | `income_day_of_month` | Integer (or -1 if missing). | Helps predict *when* a retry is likely to succeed (regression target). |
| `account_age_months` | `account_age_months` | Float cast. | Older accounts may have more stable financial patterns. |

---

## 2. Transaction / Financial Features
Derived from `transactions.csv`, rigidly filtered to `transaction.date <= attempt_date`.

| Feature | Logic (Prior to attempt) | Why it predicts recovery |
|---|---|---|
| `balance_at_attempt` | Value at failure event. | Starting point for recovery distance. |
| `mandate_amount` | The target amount. | - |
| `amount_shortfall` | `max(0, mandate_amount - balance_at_attempt)` | Exact delta needed. Smaller shortfalls recover faster. |
| `balance_to_mandate_ratio` | `balance_at_attempt / mandate_amount` | Liquidity indicator. |
| `recent_inflow_totals` | Sum of credits (last 30 days). | Shows recent cash generation. |
| `recent_outflow_totals` | Sum of debits (last 30 days). | Shows recent burn rate. |
| `recent_net_cash_flow` | Inflows - Outflows. | Positive flow indicates accumulation of funds. |
| `avg/min/max_historical_balance` | Aggregates over all past history. | Baseline financial health. |
| `recent_balance_trend` | Current balance minus avg recent balance. | Indicates if the user is trending up or down financially. |
| `num_credit/debit_txns` | Count over last 30 days. | Activity levels. |
| `recent_significant_inflows` | Count of credits $\ge$ mandate_amount (or 1000). | Proxies salary or gig payouts. |
| `days_since_last_significant_inflow` | Days since the last large credit. | If it's been 29 days, payday is likely tomorrow. |

---

## 3. Mandate / Payment Features
Derived from `mandates.csv` and `mandate_attempts.csv`, strictly filtered for attempts `< attempt_date`.

| Feature | Logic | Why it predicts recovery |
|---|---|---|
| `mandate_frequency` | `frequency` | Standard AutoPay metadata. |
| `mandate_status` | `status` | If revoked/paused, recovery is logically impossible via retry. |
| `mandate_due_day` | `due_day_of_month` | Determines the recurring cycle. |
| `previous_attempt_count` | Total past attempts for this mandate. | - |
| `previous_successful_attempts` | Past successful count. | Historical reliability. |
| `previous_failed_attempts` | Past failure count. | Chronic failures indicate low future recovery. |
| `previous_retry_count` | Count of attempts where `attempt_number > 1`. | Indicates reliance on the recovery system in the past. |
| `current_attempt_number` | Passed from the current failure event. | Higher attempt numbers yield diminishing returns. |
| `failure_reason` | E.g., INSUFFICIENT_BALANCE vs TECHNICAL_FAILURE. | Technical failures recover instantly. |
