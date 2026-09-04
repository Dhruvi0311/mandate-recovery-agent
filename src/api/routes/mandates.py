import os
import pandas as pd
from typing import List
from fastapi import APIRouter, Depends, HTTPException

from src.api.schemas import MandateSummaryResponse, MandateDetailResponse
from src.api.dependencies import (
    get_data_dir,
    get_outcome_service,
    get_conversation_store,
    OutcomeService,
    ConversationStore
)

router = APIRouter(prefix="/api/mandates", tags=["Mandates"])

def _load_attempts_df(data_dir: str) -> pd.DataFrame:
    csv_path = os.path.join(data_dir, "mandate_attempts.csv")
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=500, detail="Mandate attempts dataset not found.")
    return pd.read_csv(csv_path)

@router.get("", response_model=List[MandateSummaryResponse])
def get_mandates(
    data_dir: str = Depends(get_data_dir),
    outcome_service: OutcomeService = Depends(get_outcome_service)
) -> List[MandateSummaryResponse]:
    """
    Returns failed/relevant mandate attempts for the merchant dashboard.
    Enriches each attempt with current SQLite recovery state.
    Ground-truth fields are strictly excluded.
    """
    df = _load_attempts_df(data_dir)
    # Filter to failed attempts relevant for mandate recovery
    failed_df = df[df["status"] == "FAILED"].copy() if "status" in df.columns else df.copy()
    
    results = []
    for _, row in failed_df.iterrows():
        attempt_id = str(row["attempt_id"])
        state = outcome_service.get_state(attempt_id)
        recovery_state = state.get("status", "PENDING") if state else "PENDING"
        
        attempt_date_str = str(row.get("attempt_date", ""))
        amount_val = float(row.get("amount_required", 0.0))
        
        results.append(MandateSummaryResponse(
            attempt_id=attempt_id,
            customer_id=str(row.get("customer_id", "")),
            mandate_id=str(row.get("mandate_id", "")),
            amount=amount_val,
            attempt_date=attempt_date_str,
            failure_reason=str(row.get("failure_reason", "UNKNOWN")),
            recovery_state=recovery_state
        ))
    return results

@router.get("/{attempt_id}", response_model=MandateDetailResponse)
def get_mandate_detail(
    attempt_id: str,
    data_dir: str = Depends(get_data_dir),
    outcome_service: OutcomeService = Depends(get_outcome_service),
    conv_store: ConversationStore = Depends(get_conversation_store)
) -> MandateDetailResponse:
    """
    Returns detailed information for a single mandate attempt.
    Ground-truth fields are strictly excluded.
    """
    df = _load_attempts_df(data_dir)
    matching = df[df["attempt_id"] == attempt_id]
    if matching.empty:
        raise HTTPException(status_code=404, detail=f"Mandate attempt '{attempt_id}' not found.")
        
    row = matching.iloc[0]
    state = outcome_service.get_state(attempt_id)
    recovery_state = state.get("status", "PENDING") if state else "PENDING"
    
    # Check if analysis has been performed and stored
    analysis = conv_store.get_analysis(attempt_id)
    decision = analysis.get("decision") if analysis else None
    recommended_retry_date = analysis.get("recommended_retry_date") if analysis else (state.get("scheduled_date") if state else None)
    recovery_probability = analysis.get("recovery_probability") if analysis else None

    return MandateDetailResponse(
        attempt_id=attempt_id,
        customer_id=str(row.get("customer_id", "")),
        mandate_id=str(row.get("mandate_id", "")),
        merchant_name=str(row.get("merchant_name", "UNKNOWN")),
        amount=float(row.get("amount_required", 0.0)),
        attempt_date=str(row.get("attempt_date", "")),
        attempt_number=int(row.get("attempt_number", 1)),
        balance_at_attempt=float(row.get("balance_at_attempt", 0.0)),
        failure_reason=str(row.get("failure_reason", "UNKNOWN")),
        recovery_state=recovery_state,
        decision=decision,
        recommended_retry_date=recommended_retry_date,
        recovery_probability=recovery_probability
    )
