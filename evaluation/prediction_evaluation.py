import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.metrics import roc_auc_score, f1_score, precision_score, recall_score, confusion_matrix

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.features.feature_pipeline import FeaturePipeline
from src.prediction.recovery_model import RecoveryModel
from src.prediction.retry_window import RetryWindowPredictor

DATA_DIR = r"c:\Users\Dhruvi Sharma\mandate-recovery-agent\data"
MODEL_DIR = r"c:\Users\Dhruvi Sharma\mandate-recovery-agent\src\prediction\models"

def load_and_split_data():
    pipeline = FeaturePipeline(DATA_DIR)
    
    print("Generating features for all failed attempts...")
    X_df, y_df = pipeline.generate_features_for_training()
    
    # Merge for time-aware splitting
    df = pd.merge(X_df, y_df, on='attempt_id')
    
    # Fetch attempt_date from original dataset for time splitting
    df = pd.merge(df, pipeline.attempts_df[['attempt_id', 'attempt_date']], on='attempt_id')
    df = df.sort_values(by='attempt_date')
    
    # Convert string targets to boolean/int if necessary
    if df['ground_truth_recoverable'].dtype == object:
        df['ground_truth_recoverable'] = df['ground_truth_recoverable'].astype(str).str.upper() == 'TRUE'
        
    y = df['ground_truth_recoverable'].astype(int)
    
    # Time-aware split: 80% train, 20% test based on time
    split_idx = int(len(df) * 0.8)
    X_train = df.iloc[:split_idx].drop(columns=['ground_truth_recoverable', 'ground_truth_retry_date', 'attempt_date'])
    y_train = y.iloc[:split_idx]
    
    X_test = df.iloc[split_idx:].drop(columns=['ground_truth_recoverable', 'ground_truth_retry_date', 'attempt_date'])
    y_test = y.iloc[split_idx:]
    
    return X_train, X_test, y_train, y_test, df.iloc[split_idx:], pipeline

def build_preprocessor(X):
    # Identify numerical and categorical columns, ignore ID columns
    ignored_cols = ['attempt_id', 'customer_id', 'mandate_id']
    feature_cols = [c for c in X.columns if c not in ignored_cols]
    
    num_cols = X[feature_cols].select_dtypes(include=['int64', 'float64']).columns.tolist()
    cat_cols = X[feature_cols].select_dtypes(include=['object', 'category']).columns.tolist()
    
    num_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())
    ])
    
    cat_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='constant', fill_value='missing')),
        ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
    ])
    
    preprocessor = ColumnTransformer(
        transformers=[
            ('num', num_transformer, num_cols),
            ('cat', cat_transformer, cat_cols)
        ])
        
    return preprocessor, feature_cols

def evaluate_classification(model_name, model, X_test, y_test):
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    
    print(f"\n--- {model_name} Results ---")
    try:
        auc = roc_auc_score(y_test, y_prob)
        print(f"ROC-AUC:   {auc:.3f}")
    except ValueError:
        print("ROC-AUC:   N/A (Only one class in y_test)")
        
    print(f"F1 Score:  {f1_score(y_test, y_pred):.3f}")
    print(f"Precision: {precision_score(y_test, y_pred, zero_division=0):.3f}")
    print(f"Recall:    {recall_score(y_test, y_pred, zero_division=0):.3f}")
    print("Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred))

def evaluate_retry_window(test_df, pipeline, recovery_wrapper):
    print("\n--- Retry Window Evaluation ---")
    predictor = RetryWindowPredictor(recovery_wrapper, pipeline)
    
    baseline_hits = 0
    model_hits = 0
    valid_cases = 0
    
    model_errors = []
    baseline_errors = []
    
    for _, row in test_df.iterrows():
        if pd.isna(row['ground_truth_retry_date']) or row['ground_truth_retry_date'] == "":
            continue # Skip unrecoverable cases for window evaluation
            
        valid_cases += 1
        gt_date = pd.to_datetime(row['ground_truth_retry_date'])
        attempt_date = pd.to_datetime(row['attempt_date'])
        
        # 1. Baseline: Fixed +2 days
        baseline_date = attempt_date + pd.Timedelta(days=2)
        
        # 2. Model Prediction
        res = predictor.predict_optimal_window(row['attempt_id'])
        model_date = pd.to_datetime(res['recommended_retry_date'])
        
        # Metrics: We score a "hit" if the retry date is on or after the ground truth date
        # (Because retrying before the money is there fails. Retrying on/after succeeds).
        if baseline_date >= gt_date:
            baseline_hits += 1
        if model_date >= gt_date:
            model_hits += 1
            
        baseline_errors.append(abs((baseline_date - gt_date).days))
        model_errors.append(abs((model_date - gt_date).days))

    if valid_cases > 0:
        print(f"Total valid recoverable test cases: {valid_cases}")
        print(f"Baseline (+2 days) Hit Rate:  {baseline_hits/valid_cases:.1%}")
        print(f"Model Smart Retry Hit Rate:   {model_hits/valid_cases:.1%}")
        print(f"Baseline MAE (days):          {np.mean(baseline_errors):.1f}")
        print(f"Model MAE (days):             {np.mean(model_errors):.1f}")
    else:
        print("No valid cases in test set to evaluate retry window.")

def main():
    print("Loading data and generating features...")
    X_train, X_test, y_train, y_test, test_df, pipeline = load_and_split_data()
    
    preprocessor, features_order = build_preprocessor(X_train)
    
    # Preprocess
    X_train_transformed = preprocessor.fit_transform(X_train)
    X_test_transformed = preprocessor.transform(X_test)
    
    # 1. Train Logistic Regression
    lr_model = LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42)
    lr_model.fit(X_train_transformed, y_train)
    evaluate_classification("Logistic Regression", lr_model, X_test_transformed, y_test)
    
    # 2. Train Random Forest
    rf_model = RandomForestClassifier(n_estimators=100, class_weight='balanced', random_state=42)
    rf_model.fit(X_train_transformed, y_train)
    evaluate_classification("Random Forest", rf_model, X_test_transformed, y_test)
    
    # Select best model (arbitrarily picking RF here for robust non-linear patterns)
    best_model = rf_model
    print("\nSaving Random Forest as the primary MVP model...")
    
    wrapper = RecoveryModel()
    wrapper.model = best_model
    wrapper.save(MODEL_DIR, preprocessor, features_order)
    
    # Verify load
    wrapper.load(MODEL_DIR)
    
    print("\nTop 5 Important Features:")
    importances = wrapper.get_feature_importance()
    for i, (k, v) in enumerate(importances.items()):
        if i >= 5: break
        print(f"  {k}: {v:.4f}")
        
    # Evaluate window prediction
    evaluate_retry_window(test_df, pipeline, wrapper)

if __name__ == "__main__":
    main()
