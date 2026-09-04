from fastapi import APIRouter, Depends, Query
from src.api.schemas import BatchReportResponse
from src.api.dependencies import get_batch_evaluator

router = APIRouter(prefix="/api/batch-report", tags=["Batch Report"])

@router.get("", response_model=BatchReportResponse)
def get_batch_report(
    force_recompute: bool = Query(default=False, description="Forces re-running the batch simulation"),
    evaluator=Depends(get_batch_evaluator)
) -> BatchReportResponse:
    """
    Returns the comprehensive batch recovery report comparing the Intelligent Recovery Strategy
    against the Naive +2-Day Baseline across all failed mandate attempts.
    Backed by a persisted report artifact for high performance.
    """
    report = evaluator.load_or_compute(force_recompute=force_recompute)
    return BatchReportResponse(**report)
