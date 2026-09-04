from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from src.api.schemas import AuditLogResponse, AuditRecord
from src.api.dependencies import get_audit_service

router = APIRouter(prefix="/api/audit-log", tags=["Safety & Audit"])

@router.get("", response_model=AuditLogResponse)
def get_audit_log(
    attempt_id: Optional[str] = Query(default=None, description="Optional attempt ID filter"),
    limit: int = Query(default=50, ge=1, le=200, description="Max records to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    audit_service=Depends(get_audit_service)
) -> AuditLogResponse:
    """
    Returns the complete chronological audit trail across recovery attempts.
    Highlights safety boundaries: rule evaluation -> consent check -> requested action -> tool validation (accepted vs blocked) -> execution.
    Ground-truth fields are strictly excluded.
    """
    res = audit_service.get_all(attempt_id=attempt_id, limit=limit, offset=offset)
    return AuditLogResponse(**res)

@router.get("/{attempt_id}", response_model=AuditRecord)
def get_attempt_audit_record(
    attempt_id: str,
    audit_service=Depends(get_audit_service)
) -> AuditRecord:
    """
    Returns the detailed chronological audit trail for a specific recovery attempt.
    Ground-truth fields are strictly excluded.
    """
    record = audit_service.get_record(attempt_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Audit record for attempt '{attempt_id}' not found.")
    return AuditRecord(**record)
