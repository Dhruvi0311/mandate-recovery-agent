import pickle
import os
import pandas as pd
from typing import Dict, Any, List

class RecoveryModel:
    def __init__(self, model_dir: str = None):
        """
        Wrapper for the trained recovery prediction ML model.
        """
        self.model = None
        self.preprocessor = None
        self.features_order = None
        
        if model_dir:
            self.load(model_dir)

    def load(self, model_dir: str):
        """Loads the trained model artifacts."""
        model_path = os.path.join(model_dir, 'recovery_classifier.pkl')
        meta_path = os.path.join(model_dir, 'recovery_meta.pkl')
        
        if os.path.exists(model_path) and os.path.exists(meta_path):
            with open(model_path, 'rb') as f:
                self.model = pickle.load(f)
            with open(meta_path, 'rb') as f:
                meta = pickle.load(f)
                self.preprocessor = meta['preprocessor']
                self.features_order = meta['features_order']
        else:
            raise FileNotFoundError(f"Model files not found in {model_dir}")

    def save(self, model_dir: str, preprocessor, features_order: List[str]):
        """Saves the trained model artifacts."""
        os.makedirs(model_dir, exist_ok=True)
        model_path = os.path.join(model_dir, 'recovery_classifier.pkl')
        meta_path = os.path.join(model_dir, 'recovery_meta.pkl')
        
        with open(model_path, 'wb') as f:
            pickle.dump(self.model, f)
            
        with open(meta_path, 'wb') as f:
            pickle.dump({
                'preprocessor': preprocessor,
                'features_order': features_order
            }, f)

    def predict_probability(self, feature_vector: Dict[str, Any]) -> float:
        """
        Predicts the probability of successful recovery.
        
        Args:
            feature_vector (dict): A single dictionary of features from FeaturePipeline.
            
        Returns:
            float: Probability of success (0.0 to 1.0)
        """
        if self.model is None or self.preprocessor is None:
            raise RuntimeError("Model is not loaded.")
            
        # Convert single dict to DataFrame for preprocessing
        df = pd.DataFrame([feature_vector])
        
        # Ensure we only pass the columns the model was trained on
        # and in the correct order
        for col in self.features_order:
            if col not in df.columns:
                df[col] = 0 # Default missing numericals to 0 or appropriate missing value
                
        df = df[self.features_order]
        
        X_transformed = self.preprocessor.transform(df)
        
        # Assuming binary classification where class 1 is 'True' / 'Recoverable'
        # predict_proba returns [[P(class 0), P(class 1)]]
        prob = self.model.predict_proba(X_transformed)[0][1]
        
        return float(prob)
        
    def get_feature_importance(self) -> Dict[str, float]:
        """
        Extracts interpretability metrics from the model.
        Returns a dict of feature name -> importance weight (or coefficient).
        """
        if self.model is None:
            return {}
            
        # Scikit-learn Pipeline / ColumnTransformer handling to get feature names
        try:
            # Assuming preprocessor has get_feature_names_out (sklearn >= 1.0)
            feature_names = self.preprocessor.get_feature_names_out()
        except AttributeError:
            # Fallback if get_feature_names_out is not available
            feature_names = [f"f_{i}" for i in range(len(self.features_order) * 2)] # Approximation
            
        importance_dict = {}
        
        if hasattr(self.model, 'coef_'):
            # Logistic Regression
            coefs = self.model.coef_[0]
            for name, coef in zip(feature_names, coefs):
                importance_dict[name] = float(coef)
        elif hasattr(self.model, 'feature_importances_'):
            # Random Forest / Trees
            importances = self.model.feature_importances_
            for name, imp in zip(feature_names, importances):
                importance_dict[name] = float(imp)
                
        # Sort by absolute magnitude
        return dict(sorted(importance_dict.items(), key=lambda item: abs(item[1]), reverse=True))
