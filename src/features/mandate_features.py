import pandas as pd

def calculate_mandate_features(mandate_details: dict, prior_attempts: pd.DataFrame, current_attempt_date: str) -> dict:
    """
    Calculates features related to the mandate and its historical attempts.
    
    Args:
        mandate_details: Dictionary containing mandate information (amount, merchant, frequency, status, due_day).
        prior_attempts: DataFrame of historical attempts for this specific mandate, up to the current attempt.
        current_attempt_date: The date of the current failed attempt (YYYY-MM-DD).
        
    Returns:
        dict: Mandate and attempt history features.
    """
    current_dt = pd.to_datetime(current_attempt_date)
    
    features = {
        'mandate_frequency': mandate_details.get('frequency', 'unknown'),
        'mandate_status': mandate_details.get('status', 'unknown'),
        'mandate_due_day': mandate_details.get('due_day_of_month', -1)
    }
    
    if not prior_attempts.empty:
        # STRICT TIME TRAVEL PREVENTION
        # Only look at attempts that occurred strictly BEFORE the current attempt date
        attempts = prior_attempts.copy()
        attempts['attempt_date'] = pd.to_datetime(attempts['attempt_date'])
        
        # Filter strictly less than current_dt
        past_attempts = attempts[attempts['attempt_date'] < current_dt]
        
        features['previous_attempt_count'] = len(past_attempts)
        features['previous_successful_attempts'] = len(past_attempts[past_attempts['status'] == 'SUCCESS'])
        features['previous_failed_attempts'] = len(past_attempts[past_attempts['status'] == 'FAILED'])
        
        # Retries are usually identified as attempt_number > 1
        features['previous_retry_count'] = len(past_attempts[past_attempts['attempt_number'].astype(float) > 1])
    else:
        features['previous_attempt_count'] = 0
        features['previous_successful_attempts'] = 0
        features['previous_failed_attempts'] = 0
        features['previous_retry_count'] = 0

    return features
