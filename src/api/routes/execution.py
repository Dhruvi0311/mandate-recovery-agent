from fastapi import APIRouter, Depends, HTTPException

from src.api.schemas import ExecutionResponse
from src.api.dependencies import (
    get_simulator,
    get_outcome_service,
    get_audit_service,
    PaymentSimulator,
    OutcomeService
)

router = APIRouter(prefix="/api/recovery", tags=["Execution"])

@router.post("/{attempt_id}/execute", response_model=ExecutionResponse)
def execute_scheduled_retry(
    attempt_id: str,
    simulator: PaymentSimulator = Depends(get_simulator),
    outcome_service: OutcomeService = Depends(get_outcome_service),
    audit_service = Depends(get_audit_service)
) -> ExecutionResponse:
    """
    Executes an already-authorized, SCHEDULED retry via the PaymentSimulator.
    Enforces that the attempt is in SCHEDULED state.
    """
    state = outcome_service.get_state(attempt_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Mandate attempt '{attempt_id}' has not been scheduled.")
        
    current_status = state.get("status")
    if current_status != "SCHEDULED":
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot execute retry: Attempt is in '{current_status}' state, expected 'SCHEDULED'."
        )

    res = simulator.execute_scheduled_retry(attempt_id)
    
    if res.get("result") == "ERROR":
        raise HTTPException(status_code=400, detail=res.get("reason", "Simulator execution failed."))
        
    audit_service.record_execution(
        attempt_id=attempt_id,
        execution_outcome=res.get("result", "UNKNOWN"),
        reason=res.get("reason")
    )

    return ExecutionResponse(
        attempt_id=attempt_id,
        scheduled_date=res.get("scheduled_date"),
        result=res.get("result", "UNKNOWN"),
        reason=res.get("reason")
    )
