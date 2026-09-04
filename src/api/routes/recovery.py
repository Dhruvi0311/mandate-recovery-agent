from fastapi import APIRouter, Depends, HTTPException

from src.api.schemas import (
    RecoveryAnalysisResponse,
    RecoveryStatusResponse,
    CandidateRetryWindow
)
from src.api.dependencies import (
    get_feature_pipeline,
    get_prediction_pipeline,
    get_decision_engine,
    get_outcome_service,
    get_conversation_store,
    get_audit_service,
    FeaturePipeline,
    PredictionPipeline,
    DecisionEngine,
    OutcomeService,
    ConversationStore
)
from src.decision.decision_models import DecisionInput

router = APIRouter(prefix="/api/recovery", tags=["Recovery"])

@router.post("/{attempt_id}/analyze", response_model=RecoveryAnalysisResponse)
def analyze_recovery(
    attempt_id: str,
    feature_pipeline: FeaturePipeline = Depends(get_feature_pipeline),
    prediction_pipeline: PredictionPipeline = Depends(get_prediction_pipeline),
    decision_engine: DecisionEngine = Depends(get_decision_engine),
    conv_store: ConversationStore = Depends(get_conversation_store),
    audit_service = Depends(get_audit_service)
) -> RecoveryAnalysisResponse:
    """
    Runs the full recovery intelligence pipeline:
    Feature Engine -> Prediction Engine -> Decision Engine.
    Persists decision context to state.
    Ground-truth labels are strictly excluded.
    """
    # 1. Verify attempt exists and extract features
    try:
        features = feature_pipeline.generate_features_for_inference(attempt_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Mandate attempt '{attempt_id}' not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Feature extraction failed: {str(e)}")

    # 2. Prediction Engine
    try:
        pred_recovery = prediction_pipeline.predict_recovery(attempt_id)
        recovery_prob = float(pred_recovery["recovery_probability"])
        
        retry_window = prediction_pipeline.predict_retry_window(attempt_id)
        recommended_date = retry_window.get("recommended_retry_date")
        candidate_dist = retry_window.get("candidate_distribution", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction pipeline failed: {str(e)}")

    # 3. Decision Engine
    try:
        mandate_status = features.get("mandate_status", "ACTIVE")
        current_attempt_num = int(features.get("current_attempt_number", 1))
        prior_failed_attempts = int(features.get("num_prior_failed_attempts", 0))
        failure_reason = str(features.get("failure_reason", "INSUFFICIENT_FUNDS"))
        
        decision_input = DecisionInput(
            attempt_id=attempt_id,
            recovery_probability=recovery_prob,
            recommended_retry_date=recommended_date or "",
            failure_reason=failure_reason,
            mandate_status=mandate_status,
            current_attempt_number=current_attempt_num,
            previous_failed_attempts=prior_failed_attempts
        )
        decision_output = decision_engine.evaluate(decision_input)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Decision evaluation failed: {str(e)}")

    candidate_windows = [
        CandidateRetryWindow(
            date=str(c.get("date")),
            success_probability=round(float(c.get("success_probability", 0.0)), 4)
        )
        for c in candidate_dist[:10]  # Return top 10 candidate windows for frontend display
    ]

    amount = float(features.get("mandate_amount", features.get("amount_required", 0.0)))
    if amount == 0.0:
        # Fallback to attempt row directly if not in feature vector
        matching = feature_pipeline.attempts_df[feature_pipeline.attempts_df['attempt_id'] == attempt_id]
        if not matching.empty:
            amount = float(matching.iloc[0].get("amount_required", 0.0))

    response_data = RecoveryAnalysisResponse(
        attempt_id=attempt_id,
        customer_id=str(features.get("customer_id", "")),
        mandate_id=str(features.get("mandate_id", "")),
        amount=amount,
        failure_reason=failure_reason,
        recovery_probability=round(recovery_prob, 4),
        candidate_retry_windows=candidate_windows,
        recommended_retry_date=decision_output.recommended_retry_date,
        decision=decision_output.decision,
        reason_codes=decision_output.reason_codes,
        requires_customer_consent=decision_output.requires_customer_consent
    )

    # Persist analysis in SQLite for session use and detail enrichment
    conv_store.save_analysis(attempt_id, response_data.model_dump())

    # Record decision rule and reason codes in persistent audit trail
    audit_service.record_analysis(
        attempt_id=attempt_id,
        customer_id=str(features.get("customer_id", "")),
        mandate_id=str(features.get("mandate_id", "")),
        decision=decision_output.decision,
        reason_codes=decision_output.reason_codes,
        recovery_probability=round(recovery_prob, 4),
        recommended_retry_date=decision_output.recommended_retry_date,
        consent_requirement=decision_output.requires_customer_consent,
        explanation=decision_output.explanation
    )

    return response_data

@router.get("/{attempt_id}/status", response_model=RecoveryStatusResponse)
def get_recovery_status(
    attempt_id: str,
    outcome_service: OutcomeService = Depends(get_outcome_service),
    feature_pipeline: FeaturePipeline = Depends(get_feature_pipeline)
) -> RecoveryStatusResponse:
    """
    Returns the current lifecycle state from SQLite:
    PENDING, SCHEDULED, EXECUTED, ACTION_REJECTED, etc.
    """
    state = outcome_service.get_state(attempt_id)
    if state:
        return RecoveryStatusResponse(
            attempt_id=attempt_id,
            customer_id=state.get("customer_id"),
            status=state.get("status", "PENDING"),
            scheduled_date=state.get("scheduled_date"),
            execution_time=state.get("execution_time"),
            outcome=state.get("outcome"),
            reason=state.get("reason")
        )
        
    # Check if attempt is valid in dataset
    matching = feature_pipeline.attempts_df[feature_pipeline.attempts_df['attempt_id'] == attempt_id]
    if matching.empty:
        raise HTTPException(status_code=404, detail=f"Mandate attempt '{attempt_id}' not found.")
        
    row = matching.iloc[0]
    return RecoveryStatusResponse(
        attempt_id=attempt_id,
        customer_id=str(row.get("customer_id", "")),
        status="PENDING",
        scheduled_date=None,
        execution_time=None,
        outcome=None,
        reason=None
    )
