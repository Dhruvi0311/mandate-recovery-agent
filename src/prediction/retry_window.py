import pandas as pd
from datetime import timedelta
from typing import Dict, Any, List

# Local imports
from .recovery_model import RecoveryModel
from src.features.transaction_features import calculate_transaction_features
from src.features.mandate_features import calculate_mandate_features

class RetryWindowPredictor:
    def __init__(self, model: RecoveryModel, pipeline_instance):
        """
        Args:
            model: An initialized RecoveryModel to score candidates.
            pipeline_instance: An instance of FeaturePipeline to fetch base data.
        """
        self.model = model
        self.pipeline = pipeline_instance

    def predict_optimal_window(self, attempt_id: str, max_days_ahead: int = 30) -> Dict[str, Any]:
        """
        Generates candidate dates, scores them, and returns the best window.
        """
        attempt = self.pipeline.attempts_df[self.pipeline.attempts_df['attempt_id'] == attempt_id]
        if attempt.empty:
            raise ValueError(f"Attempt ID {attempt_id} not found.")
            
        row = attempt.iloc[0]
        customer_id = row['customer_id']
        mandate_id = row['mandate_id']
        original_attempt_date = pd.to_datetime(row['attempt_date'])
        
        # Base features that don't change per candidate day
        cust_features = self.pipeline._get_customer_features(customer_id)
        
        # PREVENT LEAKAGE: Strictly clip transactions to the ORIGINAL attempt date.
        # This guarantees that even if we pass a future candidate_date to the feature 
        # engine, it physically cannot access transactions that haven't happened yet.
        all_cust_txns = self.pipeline.transactions_df[self.pipeline.transactions_df['customer_id'] == customer_id].copy()
        safe_cust_txns = all_cust_txns[all_cust_txns['date'] <= original_attempt_date]
        
        # PREVENT LEAKAGE: Same for mandate prior attempts
        all_prior_attempts = self.pipeline.attempts_df[self.pipeline.attempts_df['mandate_id'] == mandate_id].copy()
        safe_prior_attempts = all_prior_attempts[all_prior_attempts['attempt_date'] < original_attempt_date]
        
        mandate_row = self.pipeline.mandates_df[self.pipeline.mandates_df['mandate_id'] == mandate_id]
        mandate_details = mandate_row.iloc[0].to_dict() if not mandate_row.empty else {}
        
        candidates = []
        
        for day_offset in range(1, max_days_ahead + 1):
            candidate_date = original_attempt_date + timedelta(days=day_offset)
            candidate_date_str = str(candidate_date.date())
            
            # Recalculate transaction features from the perspective of the candidate date
            # It will "age" temporal features (like days_since_last_inflow)
            txn_features = calculate_transaction_features(
                customer_txns=safe_cust_txns,
                attempt_date=candidate_date_str,
                mandate_amount=float(row['amount_required']),
                balance_at_attempt=float(row['balance_at_attempt']) # We assume balance stays the same without future knowledge
            )
            
            # Recalculate mandate features
            mandate_features = calculate_mandate_features(
                mandate_details=mandate_details,
                prior_attempts=safe_prior_attempts,
                current_attempt_date=candidate_date_str
            )
            
            # Assemble feature vector
            fv = {
                'attempt_id': attempt_id,
                'customer_id': customer_id,
                'mandate_id': mandate_id,
                'merchant_name': row.get('merchant_name', 'unknown'),
                'current_attempt_number': float(row.get('attempt_number', 1.0)),
                'failure_reason': row.get('failure_reason', 'unknown'),
            }
            fv.update(cust_features)
            fv.update(txn_features)
            fv.update(mandate_features)
            
            # Score
            prob = self.model.predict_probability(fv)
            
            candidates.append({
                "date": candidate_date_str,
                "success_probability": prob
            })
            
        # Sort candidates descending by probability
        candidates.sort(key=lambda x: x['success_probability'], reverse=True)
        
        best_candidate = candidates[0]
        
        return {
            "recommended_retry_date": best_candidate["date"],
            "predicted_success_probability": best_candidate["success_probability"],
            "candidate_distribution": candidates
        }
