import unittest
import pandas as pd
from datetime import datetime, timedelta
from src.features.transaction_features import calculate_transaction_features
from src.features.mandate_features import calculate_mandate_features
from src.features.feature_pipeline import FeaturePipeline
import os

class TestFeaturePipeline(unittest.TestCase):

    def setUp(self):
        # We assume the canonical dataset exists at this path during tests.
        self.data_dir = r"c:\Users\Dhruvi Sharma\mandate-recovery-agent\data"

    def test_transaction_time_travel_prevention(self):
        """Prove that future transactions are excluded from calculations."""
        # Mock transaction data
        txns = pd.DataFrame([
            {'date': '2026-06-01', 'type': 'credit', 'amount': 1000, 'balance_after': 1000},
            {'date': '2026-06-15', 'type': 'debit', 'amount': 200, 'balance_after': 800},
            {'date': '2026-06-25', 'type': 'credit', 'amount': 500, 'balance_after': 1300}, # This is the future transaction!
        ])
        
        attempt_date = '2026-06-20'
        
        features = calculate_transaction_features(
            customer_txns=txns,
            attempt_date=attempt_date,
            mandate_amount=500.0,
            balance_at_attempt=800.0
        )
        
        # The sum of credits BEFORE 2026-06-20 is just the first transaction (1000)
        # If it leaked, it would be 1500
        self.assertEqual(features['recent_inflow_totals'], 1000.0)
        self.assertEqual(features['max_historical_balance'], 1000.0)

    def test_mandate_previous_attempts(self):
        """Prove that previous attempts are calculated strictly before the current attempt."""
        prior_attempts = pd.DataFrame([
            {'attempt_date': '2026-05-01', 'status': 'FAILED', 'attempt_number': 1},
            {'attempt_date': '2026-05-05', 'status': 'SUCCESS', 'attempt_number': 2},
            {'attempt_date': '2026-06-01', 'status': 'FAILED', 'attempt_number': 1}, # Current attempt
            {'attempt_date': '2026-06-05', 'status': 'SUCCESS', 'attempt_number': 2}, # Future attempt
        ])
        
        mandate_details = {'frequency': 'monthly', 'status': 'active', 'due_day_of_month': 1}
        
        features = calculate_mandate_features(
            mandate_details=mandate_details,
            prior_attempts=prior_attempts,
            current_attempt_date='2026-06-01'
        )
        
        # Only the two attempts in May should be counted
        self.assertEqual(features['previous_attempt_count'], 2)
        self.assertEqual(features['previous_successful_attempts'], 1)
        self.assertEqual(features['previous_failed_attempts'], 1)
        self.assertEqual(features['previous_retry_count'], 1)

    def test_missing_transaction_history(self):
        """Prove that missing or empty transaction history is handled gracefully."""
        empty_txns = pd.DataFrame()
        
        features = calculate_transaction_features(
            customer_txns=empty_txns,
            attempt_date='2026-06-20',
            mandate_amount=500.0,
            balance_at_attempt=100.0
        )
        
        self.assertEqual(features['recent_inflow_totals'], 0.0)
        self.assertEqual(features['avg_historical_balance'], 100.0) # Defaults to balance at attempt
        self.assertEqual(features['days_since_last_significant_inflow'], -1)

    def test_end_to_end_pipeline_no_leakage(self):
        """Prove that feature generation works on the real dataset and excludes prohibited fields."""
        if not os.path.exists(os.path.join(self.data_dir, "customers.csv")):
            self.skipTest("Canonical dataset not found at expected path. Skipping E2E test.")
            
        pipeline = FeaturePipeline(self.data_dir)
        
        # Pick the first failed attempt from the dataset
        failed_attempts = pipeline.attempts_df[pipeline.attempts_df['status'] == 'FAILED']
        first_failed_id = failed_attempts.iloc[0]['attempt_id']
        
        fv = pipeline.generate_features_for_inference(first_failed_id)
        
        # Assert none of the prohibited fields are in the final feature vector
        prohibited = [
            'ground_truth_recoverable', 'ground_truth_retry_date',
            'recovery_probability', 'predicted_retry_date', 
            'recommended_action', 'actual_retry_result', 'customer_response',
            'scenario_tag'
        ]
        for p in prohibited:
            self.assertNotIn(p, fv, f"Prohibited field {p} found in feature vector!")
            
        # Assert expected fields exist
        self.assertIn('recent_inflow_totals', fv)
        self.assertIn('behavior_type', fv)
        self.assertIn('previous_attempt_count', fv)

if __name__ == '__main__':
    unittest.main()
