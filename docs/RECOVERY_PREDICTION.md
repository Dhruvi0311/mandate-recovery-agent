# Recovery Prediction Engine Documentation

## 1. Problem Being Predicted
When a UPI AutoPay mandate fails, the system must independently answer two questions based purely on past transaction data:
1. **Recoverability:** What is the probability this failed attempt will eventually succeed if we retry?
2. **Retry-Window:** Exactly which date in the future gives us the highest statistical chance of a successful recovery?

## 2. Targets
- **Recoverability:** `ground_truth_recoverable` (Binary Classification Target)
- **Retry-Window:** `ground_truth_retry_date` (Regression / Date Hit Evaluation Target)

*Note: Prohibited fields like `ground_truth_recoverable`, `ground_truth_retry_date`, `recovery_probability`, `recommended_action`, and `scenario_tag` (which leaks targets like `GOLDEN_MANDATE_REVOKED`) are mathematically stripped from feature vectors before any prediction runs.*

## 3. Baseline
To demonstrate the value of this intelligent model, we compare it against a **Naive Baseline**:
- **Baseline Strategy:** The standard industry approach of a blind retry after exactly 2 days (`attempt_date + 2 days`).
- **Evaluation:** Does the $+2$ day retry hit a window where the customer actually had balance?

## 4. Features Used
The engine utilizes the `FeaturePipeline` to extract:
- **Transaction Features:** Recent cash flows, balance trends, and timing of significant inflows up to the exact `attempt_date`.
- **Mandate Features:** Previous attempt failures and amounts.
- **Customer Features:** Income cadence and behavior typologies.

## 5. Models Evaluated
The evaluation script compares two models:
1. **Logistic Regression:** Used as an interpretable linear baseline.
2. **Random Forest Classifier:** A stronger tree-based ensemble to capture non-linear relationships.

## 6. Train / Test Strategy
Because this is financial event data, the evaluation uses a **Time-Aware Split**:
- The dataset is sorted by `attempt_date`.
- The first 80% of attempts are used for training.
- The most recent 20% of attempts are held out for testing.
- This closely simulates a real-world production deployment predicting future failures based on historical patterns.

## 7. Recoverability Results
Based on the actual time-aware evaluation of the 20% holdout set, the Random Forest model significantly outperforms the linear model and achieves excellent classification metrics:

**Logistic Regression Results:**
- ROC-AUC: 0.975
- F1 Score: 0.905
- Precision: 0.864
- Recall: 0.950

**Random Forest Results (Selected MVP Model):**
- **ROC-AUC: 0.989**
- **F1 Score: 0.923**
- **Precision: 0.947**
- **Recall: 0.900**

## 8. Retry-Window Methodology
Instead of treating date prediction as a pure regression problem, we use **Candidate Date Scoring**:

For a failed attempt on date $T$:
1. Generate candidate dates $T+1 \dots T+30$.
2. **Strict Leakage Prevention:** The `transactions_df` is mathematically filtered so that only transactions occurring $\le T$ are preserved in memory. 
3. Construct point-in-time features for each candidate. Since transactions are capped at $T$, actual future deposits are invisible to the model. However, temporal features project forward logically (e.g., if a salary arrived at $T-5$, a candidate at $T+20$ will have `days_since_last_significant_inflow` = 25).
4. Pass each candidate feature vector through the trained Random Forest classifier.
5. Select the candidate date that yields the maximum probability of recovery.

## 9. Evaluation Results
The intelligent candidate scoring method identifies the correct future retry window with a higher success rate than the naive baseline. 

**Validation on 20 valid recoverable test cases:**
- **Baseline (+2 days) Hit Rate:** 70.0%
- **Model Smart Retry Hit Rate:** **75.0%**
- **Baseline MAE:** 2.6 days
- **Model MAE:** 8.1 days

*Analysis:* While the Model MAE is higher (because the model is willing to skip an entire week to wait for an upcoming predicted salary day, resulting in a large absolute date difference), this patience leads to a 5% absolute increase in the actual hit rate compared to a blind short-term retry.

## 10. Interpretability Approach
The system extracts `feature_importances_` from the Random Forest. This allows the backend to know *why* a mandate is highly recoverable. 

The top 5 most influential features measured during evaluation were:
1. `num__current_attempt_number` (0.2192) - *Diminishing returns on chronic failures.*
2. `num__previous_failed_attempts` (0.1045)
3. `cat__failure_reason_ACCOUNT_ISSUE` (0.0893)
4. `cat__mandate_status_active` (0.0496)
5. `cat__failure_reason_TECHNICAL_FAILURE` (0.0483)

## 11. How Another Component Can Call the Prediction Pipeline
```python
from src.prediction.prediction_pipeline import PredictionPipeline

# Initialize once (loads data and model)
pipeline = PredictionPipeline(data_dir="/path/to/data", model_dir="/path/to/models")

# Get probability of recovery
recovery_result = pipeline.predict_recovery("ATMPT00001")
print(recovery_result['recovery_probability']) # e.g., 0.86

# Get the recommended future date
window_result = pipeline.predict_retry_window("ATMPT00001")
print(window_result['recommended_retry_date']) # e.g., "2026-07-01"
```
