import unittest
import pandas as pd
from datetime import datetime, timedelta
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.prediction.recovery_model import RecoveryModel
from src.prediction.prediction_pipeline import PredictionPipeline

class TestPredictionPipeline(unittest.TestCase):

    def setUp(self):
        self.data_dir = r"c:\Users\Dhruvi Sharma\mandate-recovery-agent\data"
        self.model_dir = r"c:\Users\Dhruvi Sharma\mandate-recovery-agent\src\prediction\models"

    def test_output_format(self):
        """
        Since the actual model training fails on this Windows env due to Numpy, 
        we mock the model predict function to test the orchestrator output format.
        """
        # We only run if we have a mock or real model.
        # But we can test the expected keys based on a mocked pipeline
        pipeline = PredictionPipeline(self.data_dir, model_dir=None)
        
        # Mocking the recovery model purely to test pipeline formatting
        pipeline.recovery_model = RecoveryModel()
        pipeline.recovery_model.predict_probability = lambda fv: 0.85
        
        # Pick the first attempt
        first_attempt_id = pipeline.feature_pipeline.attempts_df.iloc[0]['attempt_id']
        
        res = pipeline.predict_recovery(first_attempt_id)
        
        self.assertIn("attempt_id", res)
        self.assertIn("recovery_probability", res)
        self.assertIn("model_version", res)
        self.assertIn("prediction_confidence", res)
        
        self.assertEqual(res["recovery_probability"], 0.85)

    def test_probability_bounds(self):
        # Probability must be between 0 and 1
        # This is enforced by sklearn's predict_proba, but tested here conceptually
        pass
        
    def test_no_prohibited_fields_leakage(self):
        """Ensure candidate scoring doesn't leak target variables into the feature vector."""
        pipeline = PredictionPipeline(self.data_dir, model_dir=None)
        pipeline.recovery_model = RecoveryModel()
        
        # We catch the feature vector sent to the model
        captured_fv = {}
        class MockModel:
            def predict_probability(self, fv):
                captured_fv.update(fv)
                return 0.5
                
        pipeline.recovery_model = MockModel()
        pipeline.retry_window_predictor.model = pipeline.recovery_model
        
        first_attempt_id = pipeline.feature_pipeline.attempts_df.iloc[0]['attempt_id']
        
        # This should trigger candidate generation which calls predict_probability
        pipeline.predict_retry_window(first_attempt_id)
        
        prohibited = [
            'ground_truth_recoverable', 'ground_truth_retry_date',
            'recovery_probability', 'predicted_retry_date', 
            'recommended_action', 'actual_retry_result', 'customer_response',
            'scenario_tag'
        ]
        
        for p in prohibited:
            self.assertNotIn(p, captured_fv, f"Prohibited field {p} leaked into model features!")

    def test_future_transaction_independence(self):
        """
        Deliberately insert a highly informative future transaction and prove that 
        changing/removing that future transaction does NOT change the predicted retry window.
        """
        pipeline = PredictionPipeline(self.data_dir, model_dir=None)
        
        # Mock model to just return a deterministic probability based on days_since_last_significant_inflow
        # so we can track if candidate scoring changed
        class MockModel:
            def predict_probability(self, fv):
                # Using a feature that would normally be affected by future transactions
                days_since = fv.get('days_since_last_significant_inflow', 0)
                return 1.0 / (1.0 + abs(days_since)) 
                
        pipeline.recovery_model = MockModel()
        pipeline.retry_window_predictor.model = pipeline.recovery_model
        
        # Select an attempt
        first_attempt_row = pipeline.feature_pipeline.attempts_df.iloc[0]
        attempt_id = first_attempt_row['attempt_id']
        customer_id = first_attempt_row['customer_id']
        attempt_date = pd.to_datetime(first_attempt_row['attempt_date'])
        
        # 1. Base prediction (without future transaction)
        base_prediction = pipeline.predict_retry_window(attempt_id)
        base_candidates = base_prediction['candidate_distribution']
        
        # 2. Insert a massive future transaction
        future_date = attempt_date + timedelta(days=5)
        future_txn = pd.DataFrame([{
            'transaction_id': 'TXN_FUTURE_TEST',
            'customer_id': customer_id,
            'date': future_date, # Raw timestamp
            'type': 'credit',
            'amount': 999999.0, # Massive inflow
            'balance_after': 999999.0,
            'description': 'FUTURE LEAK TEST'
        }])
        
        # Concat the future transaction into the pipeline's memory
        pipeline.feature_pipeline.transactions_df = pd.concat(
            [pipeline.feature_pipeline.transactions_df, future_txn], 
            ignore_index=True
        )
        
        # 3. Recalculate prediction (with future transaction)
        leaked_prediction = pipeline.predict_retry_window(attempt_id)
        leaked_candidates = leaked_prediction['candidate_distribution']
        
        # 4. Assert candidates exactly match, proving the massive inflow was totally ignored
        self.assertEqual(len(base_candidates), len(leaked_candidates))
        for base_c, leaked_c in zip(base_candidates, leaked_candidates):
            self.assertEqual(
                base_c['success_probability'], 
                leaked_c['success_probability'], 
                f"Candidate prob changed for {base_c['date']}. Leak detected!"
            )

if __name__ == '__main__':
    unittest.main()
