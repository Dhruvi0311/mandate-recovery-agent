import os
import pandas as pd
from .transaction_features import calculate_transaction_features
from .mandate_features import calculate_mandate_features

class FeaturePipeline:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self._load_data()

    def _load_data(self):
        """Loads canonical datasets strictly without labels in features."""
        self.customers_df = pd.read_csv(os.path.join(self.data_dir, "customers.csv"))
        self.transactions_df = pd.read_csv(os.path.join(self.data_dir, "transactions.csv"))
        self.mandates_df = pd.read_csv(os.path.join(self.data_dir, "mandates.csv"))
        self.attempts_df = pd.read_csv(os.path.join(self.data_dir, "mandate_attempts.csv"))
        
        # Ensure dates are parsed
        self.transactions_df['date'] = pd.to_datetime(self.transactions_df['date'])
        self.attempts_df['attempt_date'] = pd.to_datetime(self.attempts_df['attempt_date'])

    def _get_customer_features(self, customer_id: str) -> dict:
        cust = self.customers_df[self.customers_df['customer_id'] == customer_id]
        if cust.empty:
            return {}
        
        row = cust.iloc[0]
        # EXCLUDE scenario_tag to prevent data leakage (as per PRD/Contract)
        return {
            'behavior_type': row.get('behavior_type', 'unknown'),
            'avg_monthly_income': float(row.get('avg_monthly_income', 0.0)),
            'income_day_of_month': row.get('income_day_of_month', -1),
            'account_age_months': float(row.get('account_age_months', 0.0))
        }

    def generate_features_for_inference(self, attempt_id: str) -> dict:
        """
        Generates a feature vector for a single failed attempt, used during live agent inference.
        """
        attempt = self.attempts_df[self.attempts_df['attempt_id'] == attempt_id]
        if attempt.empty:
            raise ValueError(f"Attempt ID {attempt_id} not found.")
            
        row = attempt.iloc[0]
        
        customer_id = row['customer_id']
        mandate_id = row['mandate_id']
        attempt_date_str = str(row['attempt_date'].date()) if isinstance(row['attempt_date'], pd.Timestamp) else str(row['attempt_date'])
        
        # 1. Customer Features
        cust_features = self._get_customer_features(customer_id)
        
        # 2. Transaction Features (Strictly <= attempt_date)
        cust_txns = self.transactions_df[self.transactions_df['customer_id'] == customer_id]
        txn_features = calculate_transaction_features(
            customer_txns=cust_txns,
            attempt_date=attempt_date_str,
            mandate_amount=float(row['amount_required']),
            balance_at_attempt=float(row['balance_at_attempt'])
        )
        
        # 3. Mandate Features (Prior attempts strictly < attempt_date)
        mandate_row = self.mandates_df[self.mandates_df['mandate_id'] == mandate_id]
        mandate_details = mandate_row.iloc[0].to_dict() if not mandate_row.empty else {}
        
        prior_attempts = self.attempts_df[self.attempts_df['mandate_id'] == mandate_id]
        mandate_features = calculate_mandate_features(
            mandate_details=mandate_details,
            prior_attempts=prior_attempts,
            current_attempt_date=attempt_date_str
        )
        
        # Combine all features
        feature_vector = {
            'attempt_id': attempt_id,
            'customer_id': customer_id,
            'mandate_id': mandate_id,
            'merchant_name': row.get('merchant_name', 'unknown'),
            'current_attempt_number': float(row.get('attempt_number', 1.0)),
            'failure_reason': row.get('failure_reason', 'unknown'),
        }
        
        feature_vector.update(cust_features)
        feature_vector.update(txn_features)
        feature_vector.update(mandate_features)
        
        # Explicitly ensure no prohibited ground_truth labels exist in the output vector
        prohibited_keys = [
            'ground_truth_recoverable', 'ground_truth_retry_date', 
            'recovery_probability', 'predicted_retry_date', 
            'recommended_action', 'actual_retry_result', 'customer_response',
            'scenario_tag'
        ]
        for key in prohibited_keys:
            feature_vector.pop(key, None)
            
        return feature_vector

    def generate_features_for_training(self) -> pd.DataFrame:
        """
        Generates feature vectors for all FAILED attempts to build a training dataset.
        Includes ground_truth labels separately for supervised learning.
        """
        failed_attempts = self.attempts_df[self.attempts_df['status'] == 'FAILED']
        
        features_list = []
        labels_list = []
        
        for _, row in failed_attempts.iterrows():
            attempt_id = row['attempt_id']
            # Compute point-in-time features safely
            fv = self.generate_features_for_inference(attempt_id)
            features_list.append(fv)
            
            # Extract labels purely for training, separated from features
            labels_list.append({
                'attempt_id': attempt_id,
                'ground_truth_recoverable': row.get('ground_truth_recoverable', False),
                'ground_truth_retry_date': row.get('ground_truth_retry_date', None)
            })
            
        features_df = pd.DataFrame(features_list)
        labels_df = pd.DataFrame(labels_list)
        
        return features_df, labels_df
