import pandas as pd
from datetime import timedelta

def calculate_transaction_features(customer_txns: pd.DataFrame, attempt_date: str, mandate_amount: float, balance_at_attempt: float) -> dict:
    """
    Calculates financial features based on transactions STRICTLY before or on the attempt_date.
    
    Args:
        customer_txns: DataFrame of a single customer's transactions.
        attempt_date: The date of the failed attempt (YYYY-MM-DD).
        mandate_amount: The required amount for the mandate.
        balance_at_attempt: The balance at the time of the failure.
        
    Returns:
        dict: A dictionary of transaction-based features.
    """
    attempt_dt = pd.to_datetime(attempt_date)
    
    # 1. STRICT TIME TRAVEL PREVENTION
    # Filter transactions strictly to <= attempt_date
    if not customer_txns.empty:
        # Ensure date is datetime
        txns = customer_txns.copy()
        txns['date'] = pd.to_datetime(txns['date'])
        past_txns = txns[txns['date'] <= attempt_dt].sort_values(by='date')
    else:
        past_txns = pd.DataFrame(columns=['date', 'type', 'amount', 'balance_after'])
        
    features = {
        'balance_at_attempt': balance_at_attempt,
        'mandate_amount': mandate_amount,
        'amount_shortfall': max(0.0, mandate_amount - balance_at_attempt),
        'balance_to_mandate_ratio': balance_at_attempt / mandate_amount if mandate_amount > 0 else 0.0,
    }
    
    if past_txns.empty:
        features.update({
            'recent_inflow_totals': 0.0,
            'recent_outflow_totals': 0.0,
            'recent_net_cash_flow': 0.0,
            'avg_historical_balance': balance_at_attempt,
            'min_historical_balance': balance_at_attempt,
            'max_historical_balance': balance_at_attempt,
            'recent_balance_trend': 0.0,
            'num_credit_txns': 0,
            'num_debit_txns': 0,
            'recent_significant_inflows': 0,
            'days_since_last_significant_inflow': -1
        })
        return features

    # Historical balances
    features['avg_historical_balance'] = past_txns['balance_after'].mean()
    features['min_historical_balance'] = past_txns['balance_after'].min()
    features['max_historical_balance'] = past_txns['balance_after'].max()
    
    # Recent activity (last 30 days)
    thirty_days_ago = attempt_dt - pd.Timedelta(days=30)
    recent_txns = past_txns[past_txns['date'] >= thirty_days_ago]
    
    if not recent_txns.empty:
        credits = recent_txns[recent_txns['type'] == 'credit']
        debits = recent_txns[recent_txns['type'] == 'debit']
        
        inflow = credits['amount'].sum()
        outflow = debits['amount'].sum()
        
        features['recent_inflow_totals'] = inflow
        features['recent_outflow_totals'] = outflow
        features['recent_net_cash_flow'] = inflow - outflow
        features['num_credit_txns'] = len(credits)
        features['num_debit_txns'] = len(debits)
        
        # Significant inflows (e.g. salary or gig payouts) - arbitrarily choosing > mandate_amount or > 1000
        significant_threshold = max(mandate_amount, 1000.0)
        sig_inflows = credits[credits['amount'] >= significant_threshold]
        features['recent_significant_inflows'] = len(sig_inflows)
        
        if not sig_inflows.empty:
            last_inflow_date = sig_inflows['date'].max()
            features['days_since_last_significant_inflow'] = (attempt_dt - last_inflow_date).days
        else:
            features['days_since_last_significant_inflow'] = -1
            
        # Recent balance trend: Current balance minus average of the recent period
        features['recent_balance_trend'] = balance_at_attempt - recent_txns['balance_after'].mean()
    else:
        features.update({
            'recent_inflow_totals': 0.0,
            'recent_outflow_totals': 0.0,
            'recent_net_cash_flow': 0.0,
            'num_credit_txns': 0,
            'num_debit_txns': 0,
            'recent_significant_inflows': 0,
            'days_since_last_significant_inflow': -1,
            'recent_balance_trend': 0.0
        })

    return features
