import pandas as pd
from typing import Dict, Any
from datetime import datetime
from src.simulator.outcome_service import OutcomeService

class PaymentSimulator:
    def __init__(self, outcome_service: OutcomeService, data_path: str = "data/mandate_attempts.csv"):
        self.outcome_service = outcome_service
        self.data_path = data_path
        # Do not load the dataframe globally. Read it lazily per execution to enforce isolation.

    def execute_scheduled_retry(self, attempt_id: str) -> Dict[str, Any]:
        """
        Simulates the retry by peeking at the Ground Truth oracle.
        This must ONLY be called after a successful scheduling.
        """
        state = self.outcome_service.get_state(attempt_id)
        
        if not state or state.get("status") != "SCHEDULED":
            return {"attempt_id": attempt_id, "result": "ERROR", "reason": "Attempt is not in SCHEDULED state."}
            
        customer_id = state["customer_id"]
        scheduled_date_str = state["scheduled_date"]
        scheduled_date = pd.to_datetime(scheduled_date_str)
        
        # Read the oracle
        try:
            df = pd.read_csv(self.data_path)
            attempt_row = df[df['attempt_id'] == attempt_id].iloc[0]
            
            ground_truth_recoverable = str(attempt_row['ground_truth_recoverable']).upper() == 'TRUE'
            ground_truth_retry_date = pd.to_datetime(attempt_row['ground_truth_retry_date'])
        except Exception as e:
            return {"attempt_id": attempt_id, "result": "ERROR", "reason": f"Oracle read failed: {str(e)}"}
            
        # Deterministic simulation rules
        if not ground_truth_recoverable:
            result = "FAILURE"
            reason = "Customer funds remained insufficient."
        elif pd.notnull(ground_truth_retry_date) and scheduled_date >= ground_truth_retry_date:
            result = "SUCCESS"
            reason = "Payment recovered successfully."
        else:
            result = "FAILURE"
            reason = "Retry occurred too early before funds were available."
            
        execution_time = datetime.now().isoformat()
        
        self.outcome_service.update_state(
            attempt_id=attempt_id,
            customer_id=customer_id,
            status="EXECUTED",
            execution_time=execution_time,
            outcome=result,
            reason=reason
        )
        
        return {
            "attempt_id": attempt_id,
            "scheduled_date": scheduled_date_str,
            "result": result,
            "reason": reason
        }
