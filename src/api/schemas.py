from typing import List, Optional
from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    status: str = Field(default="healthy", description="Service health status")
    service: str = Field(default="mandate-recovery-agent", description="Service identifier")
    version: str = Field(default="1.0.0", description="API version")

class MandateSummaryResponse(BaseModel):
    attempt_id: str
    customer_id: str
    mandate_id: str
    amount: float
    attempt_date: str
    failure_reason: str
    recovery_state: str

class MandateDetailResponse(BaseModel):
    attempt_id: str
    customer_id: str
    mandate_id: str
    merchant_name: str
    amount: float
    attempt_date: str
    attempt_number: int
    balance_at_attempt: float
    failure_reason: str
    recovery_state: str
    decision: Optional[str] = None
    recommended_retry_date: Optional[str] = None
    recovery_probability: Optional[float] = None

class CandidateRetryWindow(BaseModel):
    date: str
    success_probability: float

class RecoveryAnalysisResponse(BaseModel):
    attempt_id: str
    customer_id: str
    mandate_id: str
    amount: float
    failure_reason: str
    recovery_probability: float
    candidate_retry_windows: List[CandidateRetryWindow]
    recommended_retry_date: Optional[str] = None
    decision: str
    reason_codes: List[str]
    requires_customer_consent: bool

class AgentMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Message from customer or operator")

class AgentMessageResponse(BaseModel):
    attempt_id: str
    response: str
    action_status: str
    recovery_state: str
    consent_granted: bool
    messages: List[str]

class RecoveryStatusResponse(BaseModel):
    attempt_id: str
    customer_id: Optional[str] = None
    status: str
    scheduled_date: Optional[str] = None
    execution_time: Optional[str] = None
    outcome: Optional[str] = None
    reason: Optional[str] = None

class ExecutionResponse(BaseModel):
    attempt_id: str
    scheduled_date: Optional[str] = None
    result: str
    reason: Optional[str] = None

class ErrorResponse(BaseModel):
    error: str
    detail: str

class StrategyMetrics(BaseModel):
    amount_recovered: float
    recovery_rate: float
    recovered_count: int
    retries_attempted: int

class BounceFeeMetrics(BaseModel):
    fee_per_retry: float
    fee_assumption: str
    savings_from_retries_avoided: float
    savings_from_do_not_retry: float

class BatchReportResponse(BaseModel):
    total_failed_attempts: int
    total_amount: float
    intelligent_strategy: StrategyMetrics
    naive_baseline: StrategyMetrics
    incremental_recovery: float
    retries_avoided: int
    do_not_retry_count: int
    bounce_fee: BounceFeeMetrics
    decision_breakdown: dict[str, int]
    generated_at: str

class AuditTimelineEvent(BaseModel):
    stage: str
    status: str
    label: str
    detail: str
    timestamp: str

class AuditRecord(BaseModel):
    attempt_id: str
    customer_id: str
    mandate_id: str
    timestamp: str
    decision: str
    reason_codes: List[str]
    recovery_probability: float
    recommended_retry_date: Optional[str] = None
    consent_requirement: bool
    consent_status: str
    customer_response: Optional[str] = None
    requested_action: Optional[str] = None
    validation_result: str
    validation_details: Optional[str] = None
    execution_outcome: Optional[str] = None
    lifecycle_status: str
    is_blocked: bool = False
    violation_type: Optional[str] = None
    timeline: List[AuditTimelineEvent] = []
    updated_at: str

class AuditLogResponse(BaseModel):
    total_records: int
    blocked_violations_count: int
    records: List[AuditRecord]

class RogueSimulationResponse(BaseModel):
    attempt_id: str
    agent_type: str
    attempted_action: str
    validation_result: str
    violation_type: str
    rejection_reason: str
    blocked_violations_count: int
    recovery_state: str
    audit_recorded: bool
