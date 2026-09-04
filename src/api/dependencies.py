import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional

from src.features.feature_pipeline import FeaturePipeline
from src.prediction.prediction_pipeline import PredictionPipeline
from src.decision.policy_engine import DecisionEngine
from src.decision.decision_models import DecisionOutput
from src.consent.consent_service import ConsentService
from src.simulator.outcome_service import OutcomeService
from src.simulator.mandate_scheduler import MandateScheduler
from src.simulator.payment_simulator import PaymentSimulator

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "prediction", "models"))
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "db", "app_state.db"))

class ConversationStore:
    """Manages persistence of agent conversations and recovery analyses in SQLite."""
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        dirname = os.path.dirname(self.db_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_conversations (
                    attempt_id TEXT PRIMARY KEY,
                    customer_id TEXT,
                    mandate_id TEXT,
                    decision_json TEXT,
                    messages_json TEXT,
                    consent_granted INTEGER,
                    action_status TEXT,
                    fallback_reason TEXT,
                    updated_at TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recovery_analysis (
                    attempt_id TEXT PRIMARY KEY,
                    analysis_json TEXT,
                    updated_at TEXT
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def save_conversation(self, attempt_id: str, customer_id: str, mandate_id: str,
                          decision_dict: dict, messages: list, consent_granted: bool,
                          action_status: str, fallback_reason: Optional[str] = None):
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cleaned_messages = []
            for m in (messages or []):
                if not (cleaned_messages and m == cleaned_messages[-1]):
                    cleaned_messages.append(m)

            cursor.execute("""
                INSERT INTO agent_conversations 
                (attempt_id, customer_id, mandate_id, decision_json, messages_json, consent_granted, action_status, fallback_reason, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(attempt_id) DO UPDATE SET
                    decision_json=excluded.decision_json,
                    messages_json=excluded.messages_json,
                    consent_granted=excluded.consent_granted,
                    action_status=excluded.action_status,
                    fallback_reason=excluded.fallback_reason,
                    updated_at=excluded.updated_at
            """, (
                attempt_id, customer_id, mandate_id,
                json.dumps(decision_dict),
                json.dumps(cleaned_messages),
                1 if consent_granted else 0,
                action_status,
                fallback_reason,
                now
            ))
            conn.commit()
        finally:
            conn.close()

    def get_conversation(self, attempt_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agent_conversations WHERE attempt_id = ?", (attempt_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "attempt_id": row["attempt_id"],
                "customer_id": row["customer_id"],
                "mandate_id": row["mandate_id"],
                "decision_dict": json.loads(row["decision_json"]) if row["decision_json"] else None,
                "messages": json.loads(row["messages_json"]) if row["messages_json"] else [],
                "consent_granted": bool(row["consent_granted"]),
                "action_status": row["action_status"],
                "fallback_reason": row["fallback_reason"],
                "updated_at": row["updated_at"]
            }
        finally:
            conn.close()

    def save_analysis(self, attempt_id: str, analysis: dict):
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO recovery_analysis (attempt_id, analysis_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(attempt_id) DO UPDATE SET
                    analysis_json=excluded.analysis_json,
                    updated_at=excluded.updated_at
            """, (attempt_id, json.dumps(analysis), now))
            conn.commit()
        finally:
            conn.close()

    def get_analysis(self, attempt_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT analysis_json FROM recovery_analysis WHERE attempt_id = ?", (attempt_id,))
            row = cursor.fetchone()
            if not row or not row["analysis_json"]:
                return None
            return json.loads(row["analysis_json"])
        finally:
            conn.close()

class DeterministicRecoveryLLM:
    """
    Deterministic rule-guided LLM adapter for LangGraph.
    Adheres strictly to decision context, avoids hallucinations, and triggers tools safely.
    """
    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        decision_context = state.get("decision_context")
        if hasattr(decision_context, "decision"):
            decision = decision_context.decision
            recommended_date = decision_context.recommended_retry_date
            explanation = decision_context.explanation
        elif isinstance(decision_context, dict):
            decision = decision_context.get("decision")
            recommended_date = decision_context.get("recommended_retry_date")
            explanation = decision_context.get("explanation", "")
        else:
            decision = "DO_NOT_RETRY"
            recommended_date = None
            explanation = ""

        consent_granted = state.get("consent_granted", False)
        messages = state.get("messages", [])
        last_message = messages[-1] if messages else ""

        # Customer explicitly said yes
        if consent_granted:
            if decision in ["RESCHEDULE", "RETRY_NOW"] and recommended_date:
                return {
                    "tool_calls": [{
                        "name": "schedule_retry",
                        "args": {"agreed_date": recommended_date}
                    }]
                }
            elif decision == "RETRY_NOW":
                return {
                    "tool_calls": [{
                        "name": "schedule_retry",
                        "args": {"agreed_date": recommended_date or "2026-07-01"}
                    }]
                }
            else:
                return {
                    "content": f"Understood. However, our system policy indicates: {explanation}"
                }

        # Check if customer gave negative response
        negative_words = ["no", "don't", "cancel", "not now", "stop"]
        is_negative = any(w in last_message.lower() for w in negative_words)
        if is_negative:
            return {
                "tool_calls": [{
                    "name": "trigger_fallback",
                    "args": {"fallback_type": "PAYMENT_LINK"}
                }]
            }

        # Initial turn or clarification
        if decision == "RESCHEDULE":
            return {
                "content": f"Hello! Your mandate payment failed due to insufficient funds. Our recovery model predicts optimal funds on {recommended_date}. Would you like us to schedule a retry for {recommended_date}?"
            }
        elif decision == "RETRY_NOW":
            return {
                "content": "Hello! Your mandate payment failed due to a technical glitch. Would you like us to retry the payment now?"
            }
        elif decision == "DO_NOT_RETRY":
            return {
                "content": f"Hello! {explanation} We recommend completing this payment via an alternative payment method."
            }
        elif decision == "REAUTHORIZE_MANDATE":
            return {
                "content": "Hello! Your mandate is no longer active. Please reauthorize the mandate to continue recurring payments."
            }
        else:
            return {
                "content": f"Hello! {explanation} Please let us know how you would like to proceed."
            }

    def get_initial_greeting(self, decision_context) -> str:
        """Emits the single, official initial opening greeting from the recovery agent."""
        if hasattr(decision_context, "decision"):
            decision = decision_context.decision
            recommended_date = decision_context.recommended_retry_date
            explanation = decision_context.explanation or ""
        elif isinstance(decision_context, dict):
            decision = decision_context.get("decision")
            recommended_date = decision_context.get("recommended_retry_date")
            explanation = decision_context.get("explanation", "")
        else:
            decision = "DO_NOT_RETRY"
            recommended_date = None
            explanation = ""

        if decision == "RESCHEDULE":
            return f"Hello! Your mandate payment failed due to insufficient funds. Our recovery model predicts optimal funds on {recommended_date}. Would you like us to schedule a retry for {recommended_date}?"
        elif decision == "RETRY_NOW":
            return "Hello! Your mandate payment failed due to a technical glitch. Would you like us to retry the payment now?"
        elif decision == "DO_NOT_RETRY":
            return f"Hello! {explanation} We recommend completing this payment via an alternative payment method."
        elif decision == "REAUTHORIZE_MANDATE":
            return "Hello! Your mandate is no longer active. Please reauthorize the mandate to continue recurring payments."
        else:
            return f"Hello! {explanation} Please let us know how you would like to proceed."

# Dependency providers
def get_data_dir() -> str:
    return DATA_DIR

def get_model_dir() -> str:
    return MODEL_DIR

def get_db_path() -> str:
    return DB_PATH

def get_feature_pipeline() -> FeaturePipeline:
    return FeaturePipeline(data_dir=get_data_dir())

def get_prediction_pipeline() -> PredictionPipeline:
    return PredictionPipeline(data_dir=get_data_dir(), model_dir=get_model_dir())

def get_decision_engine() -> DecisionEngine:
    return DecisionEngine()

def get_consent_service() -> ConsentService:
    return ConsentService(data_path=os.path.join(get_data_dir(), "consents.csv"))

def get_outcome_service() -> OutcomeService:
    return OutcomeService(db_path=get_db_path())

def get_scheduler() -> MandateScheduler:
    return MandateScheduler(get_consent_service(), get_outcome_service())

def get_simulator() -> PaymentSimulator:
    return PaymentSimulator(get_outcome_service(), data_path=os.path.join(get_data_dir(), "mandate_attempts.csv"))

def get_agent_llm():
    return DeterministicRecoveryLLM()

def get_conversation_store() -> ConversationStore:
    return ConversationStore(db_path=get_db_path())

def get_batch_evaluator():
    from src.evaluation.batch_evaluator import BatchEvaluator
    return BatchEvaluator(data_dir=get_data_dir(), model_dir=get_model_dir())

def get_audit_service():
    from src.audit.audit_service import AuditService
    return AuditService(db_path=get_db_path())
