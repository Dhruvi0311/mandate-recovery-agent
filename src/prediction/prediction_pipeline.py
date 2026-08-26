from typing import Dict, Any
from src.features.feature_pipeline import FeaturePipeline
from .recovery_model import RecoveryModel
from .retry_window import RetryWindowPredictor

class PredictionPipeline:
    def __init__(self, data_dir: str, model_dir: str):
        self.feature_pipeline = FeaturePipeline(data_dir=data_dir)
        self.recovery_model = RecoveryModel(model_dir=model_dir)
        self.retry_window_predictor = RetryWindowPredictor(
            model=self.recovery_model,
            pipeline_instance=self.feature_pipeline
        )

    def predict_recovery(self, attempt_id: str) -> Dict[str, Any]:
        """
        Predicts the probability of successful recovery for a given mandate attempt.
        """
        fv = self.feature_pipeline.generate_features_for_inference(attempt_id)
        prob = self.recovery_model.predict_probability(fv)
        
        # We determine confidence arbitrarily for the MVP demo based on extremes
        confidence = "HIGH" if (prob > 0.8 or prob < 0.2) else "MEDIUM"
        
        return {
            "attempt_id": attempt_id,
            "recovery_probability": prob,
            "model_version": "MVP_v1",
            "prediction_confidence": confidence
        }

    def predict_retry_window(self, attempt_id: str) -> Dict[str, Any]:
        """
        Predicts the optimal retry date by scoring future candidates.
        """
        return self.retry_window_predictor.predict_optimal_window(attempt_id)
