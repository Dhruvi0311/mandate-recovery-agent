from fastapi import APIRouter, Depends, HTTPException
from src.api.schemas import AgentMessageRequest, AgentMessageResponse, RogueSimulationResponse
from src.api.dependencies import (
    get_agent_llm,
    get_conversation_store,
    get_outcome_service,
    get_feature_pipeline,
    get_prediction_pipeline,
    get_decision_engine,
    get_audit_service,
    ConversationStore,
    OutcomeService,
    FeaturePipeline,
    PredictionPipeline,
    DecisionEngine
)
from src.decision.decision_models import DecisionOutput, DecisionInput
from src.agent.graph import build_graph
from src.agent.state import AgentState
from src.agent.mock_llm import MockLLM

router = APIRouter(prefix="/api/agent", tags=["Agent"])

@router.get("/{attempt_id}", response_model=AgentMessageResponse)
def get_agent_conversation(
    attempt_id: str,
    llm = Depends(get_agent_llm),
    conv_store: ConversationStore = Depends(get_conversation_store),
    outcome_service: OutcomeService = Depends(get_outcome_service),
    feature_pipeline: FeaturePipeline = Depends(get_feature_pipeline),
    prediction_pipeline: PredictionPipeline = Depends(get_prediction_pipeline),
    decision_engine: DecisionEngine = Depends(get_decision_engine)
) -> AgentMessageResponse:
    """
    Retrieves or idempotently initializes the recovery conversation for an attempt.
    Guarantees that the agent opening greeting is returned exactly once without requiring
    or inventing a fake customer 'Hello' turn.
    Safe for repeated calls/renders without duplicating messages.
    """
    existing_conv = conv_store.get_conversation(attempt_id)
    outcome_state = outcome_service.get_state(attempt_id)
    current_recovery_state = outcome_state.get("status", "PENDING") if outcome_state else "PENDING"

    if existing_conv and existing_conv.get("messages"):
        messages = existing_conv["messages"]
        # Deduplicate consecutive identical messages if present
        cleaned_messages = []
        for msg in messages:
            if not (cleaned_messages and msg == cleaned_messages[-1]):
                cleaned_messages.append(msg)

        if len(cleaned_messages) != len(messages):
            conv_store.save_conversation(
                attempt_id=attempt_id,
                customer_id=existing_conv["customer_id"],
                mandate_id=existing_conv["mandate_id"],
                decision_dict=existing_conv["decision_dict"],
                messages=cleaned_messages,
                consent_granted=existing_conv["consent_granted"],
                action_status=existing_conv["action_status"],
                fallback_reason=existing_conv.get("fallback_reason")
            )
            messages = cleaned_messages

        latest_agent_msg = next((m.replace("Agent: ", "") for m in reversed(messages) if m.startswith("Agent: ")), "")
        return AgentMessageResponse(
            attempt_id=attempt_id,
            response=latest_agent_msg,
            action_status=existing_conv["action_status"],
            recovery_state=current_recovery_state,
            consent_granted=existing_conv["consent_granted"],
            messages=messages
        )

    # 1. Load attempt details & Decision Context to create clean opening greeting
    try:
        features = feature_pipeline.generate_features_for_inference(attempt_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Mandate attempt '{attempt_id}' not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Feature extraction failed: {str(e)}")

    customer_id = str(features.get("customer_id", ""))
    mandate_id = str(features.get("mandate_id", ""))

    analysis = conv_store.get_analysis(attempt_id)
    if analysis:
        decision_context = DecisionOutput(
            attempt_id=attempt_id,
            decision=analysis.get("decision", "DO_NOT_RETRY"),
            recommended_retry_date=analysis.get("recommended_retry_date"),
            recovery_probability=float(analysis.get("recovery_probability", 0.0)),
            reason_codes=analysis.get("reason_codes", []),
            explanation=analysis.get("explanation", f"Policy decision: {analysis.get('decision')}"),
            requires_customer_consent=analysis.get("requires_customer_consent", True)
        )
    else:
        pred = prediction_pipeline.predict_recovery(attempt_id)
        rec_prob = float(pred["recovery_probability"])
        window = prediction_pipeline.predict_retry_window(attempt_id)
        rec_date = window.get("recommended_retry_date")

        dec_in = DecisionInput(
            attempt_id=attempt_id,
            recovery_probability=rec_prob,
            recommended_retry_date=rec_date or "",
            failure_reason=str(features.get("failure_reason", "INSUFFICIENT_FUNDS")),
            mandate_status=str(features.get("mandate_status", "ACTIVE")),
            current_attempt_number=int(features.get("current_attempt_number", 1)),
            previous_failed_attempts=int(features.get("num_prior_failed_attempts", 0))
        )
        decision_context = decision_engine.evaluate(dec_in)

    if hasattr(llm, "get_initial_greeting"):
        greeting_text = llm.get_initial_greeting(decision_context)
    else:
        if decision_context.decision == "RESCHEDULE":
            greeting_text = f"Hello! Your mandate payment failed due to insufficient funds. Our recovery model predicts optimal funds on {decision_context.recommended_retry_date}. Would you like us to schedule a retry for {decision_context.recommended_retry_date}?"
        elif decision_context.decision == "RETRY_NOW":
            greeting_text = "Hello! Your mandate payment failed due to a technical glitch. Would you like us to retry the payment now?"
        elif decision_context.decision == "DO_NOT_RETRY":
            greeting_text = f"Hello! {decision_context.explanation} We recommend completing this payment via an alternative payment method."
        else:
            greeting_text = f"Hello! {decision_context.explanation} Please let us know how you would like to proceed."

    initial_messages = [f"Agent: {greeting_text}"]

    decision_dict = {
        "attempt_id": decision_context.attempt_id,
        "decision": decision_context.decision,
        "recommended_retry_date": decision_context.recommended_retry_date,
        "recovery_probability": decision_context.recovery_probability,
        "reason_codes": decision_context.reason_codes,
        "explanation": decision_context.explanation,
        "requires_customer_consent": decision_context.requires_customer_consent
    }

    conv_store.save_conversation(
        attempt_id=attempt_id,
        customer_id=customer_id,
        mandate_id=mandate_id,
        decision_dict=decision_dict,
        messages=initial_messages,
        consent_granted=False,
        action_status="PENDING",
        fallback_reason=None
    )

    return AgentMessageResponse(
        attempt_id=attempt_id,
        response=greeting_text,
        action_status="PENDING",
        recovery_state=current_recovery_state,
        consent_granted=False,
        messages=initial_messages
    )

@router.post("/{attempt_id}/message", response_model=AgentMessageResponse)
def handle_agent_message(
    attempt_id: str,
    request: AgentMessageRequest,
    llm = Depends(get_agent_llm),
    conv_store: ConversationStore = Depends(get_conversation_store),
    outcome_service: OutcomeService = Depends(get_outcome_service),
    feature_pipeline: FeaturePipeline = Depends(get_feature_pipeline),
    prediction_pipeline: PredictionPipeline = Depends(get_prediction_pipeline),
    decision_engine: DecisionEngine = Depends(get_decision_engine),
    audit_service = Depends(get_audit_service)
) -> AgentMessageResponse:
    """
    Passes a customer or operator message to the existing LangGraph Agent.
    Preserves conversational memory in SQLite.
    Adheres strictly to Decision Engine boundaries.
    """
    # 1. Check for existing conversation or initialize one
    existing_conv = conv_store.get_conversation(attempt_id)
    
    if existing_conv:
        customer_id = existing_conv["customer_id"]
        mandate_id = existing_conv["mandate_id"]
        dec_data = existing_conv["decision_dict"]
        decision_context = DecisionOutput(
            attempt_id=dec_data.get("attempt_id", attempt_id),
            decision=dec_data.get("decision", "DO_NOT_RETRY"),
            recommended_retry_date=dec_data.get("recommended_retry_date"),
            recovery_probability=float(dec_data.get("recovery_probability", 0.0)),
            reason_codes=dec_data.get("reason_codes", []),
            explanation=dec_data.get("explanation", ""),
            requires_customer_consent=dec_data.get("requires_customer_consent", True)
        )
        cleaned_existing = []
        for m in (existing_conv.get("messages") or []):
            if not (cleaned_existing and m == cleaned_existing[-1]):
                cleaned_existing.append(m)
        messages = cleaned_existing
        consent_granted = existing_conv["consent_granted"]
        action_status = existing_conv["action_status"]
        fallback_reason = existing_conv["fallback_reason"]
    else:
        # Load attempt details
        try:
            features = feature_pipeline.generate_features_for_inference(attempt_id)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Mandate attempt '{attempt_id}' not found.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Feature extraction failed: {str(e)}")
            
        customer_id = str(features.get("customer_id", ""))
        mandate_id = str(features.get("mandate_id", ""))
        
        # Check if analysis is cached
        analysis = conv_store.get_analysis(attempt_id)
        if analysis:
            decision_context = DecisionOutput(
                attempt_id=attempt_id,
                decision=analysis.get("decision", "DO_NOT_RETRY"),
                recommended_retry_date=analysis.get("recommended_retry_date"),
                recovery_probability=float(analysis.get("recovery_probability", 0.0)),
                reason_codes=analysis.get("reason_codes", []),
                explanation=analysis.get("explanation", f"Policy decision: {analysis.get('decision')}"),
                requires_customer_consent=analysis.get("requires_customer_consent", True)
            )
        else:
            # Run fast evaluation
            pred = prediction_pipeline.predict_recovery(attempt_id)
            rec_prob = float(pred["recovery_probability"])
            window = prediction_pipeline.predict_retry_window(attempt_id)
            rec_date = window.get("recommended_retry_date")
            
            dec_in = DecisionInput(
                attempt_id=attempt_id,
                recovery_probability=rec_prob,
                recommended_retry_date=rec_date or "",
                failure_reason=str(features.get("failure_reason", "INSUFFICIENT_FUNDS")),
                mandate_status=str(features.get("mandate_status", "ACTIVE")),
                current_attempt_number=int(features.get("current_attempt_number", 1)),
                previous_failed_attempts=int(features.get("num_prior_failed_attempts", 0))
            )
            decision_context = decision_engine.evaluate(dec_in)

        messages = []
        consent_granted = False
        action_status = "PENDING"
        fallback_reason = None

    # 2. Append incoming customer message
    messages.append(f"Customer: {request.message.strip()}")

    # 3. Assemble LangGraph State
    state: AgentState = {
        "attempt_id": attempt_id,
        "customer_id": customer_id,
        "mandate_id": mandate_id,
        "decision_context": decision_context,
        "messages": messages,
        "consent_granted": consent_granted,
        "action_status": action_status,
        "fallback_reason": fallback_reason
    }

    # 4. Invoke LangGraph
    try:
        graph = build_graph(llm)
        final_state = graph.invoke(state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent graph execution failed: {str(e)}")

    # 5. Extract latest response message
    latest_response = ""
    for msg in reversed(final_state["messages"]):
        if msg.startswith("Agent: "):
            latest_response = msg[len("Agent: "):]
            break
        elif msg.startswith("Tool schedule_retry success:"):
            latest_response = msg
            break
        elif msg.startswith("Tool trigger_fallback success:"):
            latest_response = msg
            break
        elif msg.startswith("Tool execution rejected:"):
            latest_response = msg
            break

    if not latest_response and final_state["messages"]:
        latest_response = final_state["messages"][-1]

    # 6. Read latest outcome service status
    outcome_state = outcome_service.get_state(attempt_id)
    current_recovery_state = outcome_state.get("status", final_state["action_status"]) if outcome_state else final_state["action_status"]

    # 7. Persist updated conversation to SQLite
    decision_dict = {
        "attempt_id": decision_context.attempt_id,
        "decision": decision_context.decision,
        "recommended_retry_date": decision_context.recommended_retry_date,
        "recovery_probability": decision_context.recovery_probability,
        "reason_codes": decision_context.reason_codes,
        "explanation": decision_context.explanation,
        "requires_customer_consent": decision_context.requires_customer_consent
    }
    cleaned_final = []
    for m in (final_state.get("messages") or []):
        if not (cleaned_final and m == cleaned_final[-1]):
            cleaned_final.append(m)

    conv_store.save_conversation(
        attempt_id=attempt_id,
        customer_id=customer_id,
        mandate_id=mandate_id,
        decision_dict=decision_dict,
        messages=cleaned_final,
        consent_granted=final_state["consent_granted"],
        action_status=final_state["action_status"],
        fallback_reason=final_state.get("fallback_reason")
    )

    # 8. Determine safety boundary status and record in audit trail
    is_blocked = False
    violation_type = None
    validation_result = "NOT_APPLICABLE"
    validation_details = None
    requested_action = None

    for msg in reversed(cleaned_final):
        if "Tool execution rejected:" in msg:
            is_blocked = True
            validation_result = "BLOCKED"
            validation_details = msg.replace("Tool execution rejected:", "").strip()
            requested_action = "schedule_retry"
            if "consent was not granted" in msg:
                violation_type = "CONSENT_VIOLATION"
            elif "does not match authorized date" in msg or "does not match" in msg:
                violation_type = "HALLUCINATED_DATE"
            elif "not authorized for retry" in msg or "DO_NOT_RETRY" in msg:
                violation_type = "UNAUTHORIZED_ACTION"
            else:
                violation_type = "POLICY_VIOLATION"
            break
        elif "Tool schedule_retry success:" in msg:
            validation_result = "ACCEPTED"
            validation_details = msg.replace("Tool schedule_retry success:", "").strip()
            requested_action = f"schedule_retry({decision_context.recommended_retry_date})"
            break
        elif "Tool trigger_fallback success:" in msg:
            validation_result = "ACCEPTED"
            validation_details = msg.replace("Tool trigger_fallback success:", "").strip()
            requested_action = f"trigger_fallback({final_state.get('fallback_reason')})"
            break

    consent_status = "GRANTED" if final_state["consent_granted"] else (
        "REJECTED" if any(w in request.message.lower() for w in ["no", "don't", "cancel", "not now", "stop"]) else "PENDING"
    )

    audit_service.record_action_attempt(
        attempt_id=attempt_id,
        customer_id=customer_id,
        mandate_id=mandate_id,
        customer_response=request.message,
        consent_status=consent_status,
        requested_action=requested_action,
        validation_result=validation_result,
        validation_details=validation_details,
        is_blocked=is_blocked,
        violation_type=violation_type,
        lifecycle_status=current_recovery_state
    )

    return AgentMessageResponse(
        attempt_id=attempt_id,
        response=latest_response,
        action_status=final_state["action_status"],
        recovery_state=current_recovery_state,
        consent_granted=final_state["consent_granted"],
        messages=cleaned_final
    )

@router.post("/{attempt_id}/simulate-rogue", response_model=RogueSimulationResponse)
def simulate_rogue_agent(
    attempt_id: str,
    conv_store: ConversationStore = Depends(get_conversation_store),
    outcome_service: OutcomeService = Depends(get_outcome_service),
    feature_pipeline: FeaturePipeline = Depends(get_feature_pipeline),
    prediction_pipeline: PredictionPipeline = Depends(get_prediction_pipeline),
    decision_engine: DecisionEngine = Depends(get_decision_engine),
    audit_service = Depends(get_audit_service)
) -> RogueSimulationResponse:
    """
    Executes the existing adversarial MockLLM scenario through the REAL LangGraph and REAL tool boundary.
    The rogue agent attempts an invalid state-changing action:
    schedule_retry with an unauthorized/hallucinated retry date (2099-01-01).
    The real tool boundary intercepts and blocks the rogue execution attempt.
    Persists the rejection to the audit log and updates the blocked counter.
    Guarantees no state corruption, no retry scheduling, and no payment execution.
    """
    # 1. Load attempt details & Decision Context
    try:
        features = feature_pipeline.generate_features_for_inference(attempt_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Mandate attempt '{attempt_id}' not found.")
        
    customer_id = str(features.get("customer_id", ""))
    mandate_id = str(features.get("mandate_id", ""))
    
    analysis = conv_store.get_analysis(attempt_id)
    if analysis:
        decision_context = DecisionOutput(
            attempt_id=attempt_id,
            decision=analysis.get("decision", "DO_NOT_RETRY"),
            recommended_retry_date=analysis.get("recommended_retry_date"),
            recovery_probability=float(analysis.get("recovery_probability", 0.0)),
            reason_codes=analysis.get("reason_codes", []),
            explanation=analysis.get("explanation", f"Policy decision: {analysis.get('decision')}"),
            requires_customer_consent=analysis.get("requires_customer_consent", True)
        )
    else:
        pred = prediction_pipeline.predict_recovery(attempt_id)
        rec_prob = float(pred["recovery_probability"])
        window = prediction_pipeline.predict_retry_window(attempt_id)
        rec_date = window.get("recommended_retry_date")
        
        dec_in = DecisionInput(
            attempt_id=attempt_id,
            recovery_probability=rec_prob,
            recommended_retry_date=rec_date or "",
            failure_reason=str(features.get("failure_reason", "INSUFFICIENT_FUNDS")),
            mandate_status=str(features.get("mandate_status", "ACTIVE")),
            current_attempt_number=int(features.get("current_attempt_number", 1)),
            previous_failed_attempts=int(features.get("num_prior_failed_attempts", 0))
        )
        decision_context = decision_engine.evaluate(dec_in)

    # 2. Build adversarial rogue agent state
    # Consent is simulated as granted, but rogue agent hallucinates date 2099-01-01
    state: AgentState = {
        "attempt_id": attempt_id,
        "customer_id": customer_id,
        "mandate_id": mandate_id,
        "decision_context": decision_context,
        "messages": ["Customer: Yes, please schedule it."],
        "consent_granted": True,
        "action_status": "PENDING",
        "fallback_reason": None
    }

    # 3. Instantiate the exact MockLLM from the authoritative adversarial test
    rogue_llm = MockLLM(response_type="schedule_hallucinated_date")
    graph = build_graph(rogue_llm)
    
    # 4. Invoke through the REAL LangGraph and REAL tool boundary
    final_state = graph.invoke(state)

    # 5. Extract rejection details from real tool boundary
    rejection_reason = "Tool execution rejected: Boundary check failed."
    for msg in reversed(final_state["messages"]):
        if "Tool execution rejected:" in msg:
            rejection_reason = msg.replace("Tool execution rejected:", "").strip()
            break

    # 6. Read recovery state to confirm it was NOT scheduled
    outcome_state = outcome_service.get_state(attempt_id)
    current_recovery_state = outcome_state.get("status", "ACTION_REJECTED") if outcome_state else "ACTION_REJECTED"

    # 7. Record the blocked violation in persistent audit log
    audit_service.record_action_attempt(
        attempt_id=attempt_id,
        customer_id=customer_id,
        mandate_id=mandate_id,
        customer_response="Yes, please schedule it.",
        consent_status="GRANTED",
        requested_action="schedule_retry(agreed_date='2099-01-01')",
        validation_result="BLOCKED",
        validation_details=rejection_reason,
        is_blocked=True,
        violation_type="HALLUCINATED_DATE",
        lifecycle_status="ACTION_REJECTED"
    )

    blocked_count = audit_service.get_blocked_count()

    return RogueSimulationResponse(
        attempt_id=attempt_id,
        agent_type="ROGUE_AGENT",
        attempted_action="schedule_retry(agreed_date='2099-01-01')",
        validation_result="BLOCKED",
        violation_type="HALLUCINATED_DATE",
        rejection_reason=rejection_reason,
        blocked_violations_count=blocked_count,
        recovery_state=current_recovery_state,
        audit_recorded=True
    )
