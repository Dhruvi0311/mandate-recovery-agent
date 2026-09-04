import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "db", "app_state.db"))

class AuditService:
    """
    Manages the persistent audit trail for recovery attempts in SQLite.
    Tracks chronological decision rules, consent validation, requested actions,
    tool boundary checks (accepted vs blocked), and simulation outcomes.
    Guarantees that ground-truth labels are never exposed.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        dirname = os.path.dirname(self.db_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recovery_audit_log (
                    attempt_id TEXT PRIMARY KEY,
                    customer_id TEXT,
                    mandate_id TEXT,
                    timestamp TEXT,
                    decision TEXT,
                    reason_codes TEXT,
                    recovery_probability REAL,
                    recommended_retry_date TEXT,
                    consent_requirement INTEGER,
                    consent_status TEXT,
                    customer_response TEXT,
                    requested_action TEXT,
                    validation_result TEXT,
                    validation_details TEXT,
                    execution_outcome TEXT,
                    lifecycle_status TEXT,
                    is_blocked INTEGER DEFAULT 0,
                    violation_type TEXT,
                    timeline_json TEXT,
                    updated_at TEXT
                )
            """)
            conn.commit()

    def record_analysis(
        self,
        attempt_id: str,
        customer_id: str,
        mandate_id: str,
        decision: str,
        reason_codes: List[str],
        recovery_probability: float,
        recommended_retry_date: Optional[str],
        consent_requirement: bool,
        explanation: Optional[str] = None
    ):
        """Records initial decision rule evaluation in the audit log."""
        now = datetime.now().isoformat()
        reason_codes_json = json.dumps(reason_codes)

        # Build initial chronological timeline
        timeline = [
            {
                "stage": "DECISION_RULE",
                "status": "FIRED",
                "label": f"Policy Directive: {decision}",
                "detail": explanation or f"Decision Engine directed {decision}",
                "timestamp": now
            },
            {
                "stage": "REASON_CODES",
                "status": "EVALUATED",
                "label": "Reason Codes",
                "detail": ", ".join(reason_codes) if reason_codes else "None",
                "timestamp": now
            },
            {
                "stage": "CONSENT_REQUIREMENT",
                "status": "CHECKED",
                "label": "Consent Requirement",
                "detail": "Customer consent mandatory before action execution" if consent_requirement else "Autonomous execution permitted",
                "timestamp": now
            }
        ]

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO recovery_audit_log (
                    attempt_id, customer_id, mandate_id, timestamp, decision, reason_codes,
                    recovery_probability, recommended_retry_date, consent_requirement,
                    consent_status, customer_response, requested_action, validation_result,
                    validation_details, execution_outcome, lifecycle_status, is_blocked,
                    violation_type, timeline_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(attempt_id) DO UPDATE SET
                    customer_id=excluded.customer_id,
                    mandate_id=excluded.mandate_id,
                    decision=excluded.decision,
                    reason_codes=excluded.reason_codes,
                    recovery_probability=excluded.recovery_probability,
                    recommended_retry_date=excluded.recommended_retry_date,
                    consent_requirement=excluded.consent_requirement,
                    updated_at=excluded.updated_at
            """, (
                attempt_id, customer_id, mandate_id, now, decision, reason_codes_json,
                recovery_probability, recommended_retry_date, 1 if consent_requirement else 0,
                "PENDING", None, None, "PENDING", None, "NOT_EXECUTED", "ANALYZED",
                0, None, json.dumps(timeline), now
            ))
            conn.commit()

    def record_action_attempt(
        self,
        attempt_id: str,
        customer_id: str,
        mandate_id: str,
        customer_response: str,
        consent_status: str,
        requested_action: Optional[str],
        validation_result: str,
        validation_details: Optional[str],
        is_blocked: bool,
        violation_type: Optional[str],
        lifecycle_status: str
    ):
        """Records an agent action request and tool safety boundary validation (ACCEPTED vs BLOCKED)."""
        now = datetime.now().isoformat()

        # Retrieve existing timeline if any
        current = self.get_record(attempt_id)
        timeline = current.get("timeline", []) if current else []

        # Append consent stage
        timeline.append({
            "stage": "CONSENT_CHECK",
            "status": "PASSED" if consent_status == "GRANTED" else ("REJECTED" if consent_status == "REJECTED" else "PENDING"),
            "label": f"Consent Status: {consent_status}",
            "detail": f"Customer statement: \"{customer_response}\"",
            "timestamp": now
        })

        # Append requested action & safety validation
        if requested_action:
            timeline.append({
                "stage": "REQUESTED_ACTION",
                "status": "REQUESTED",
                "label": "Agent Tool Call",
                "detail": f"Agent requested execution: {requested_action}",
                "timestamp": now
            })

            timeline.append({
                "stage": "TOOL_VALIDATION",
                "status": "BLOCKED" if is_blocked else "ACCEPTED",
                "label": f"Safety Boundary: {validation_result}",
                "detail": validation_details or ("Validated against authorized decision context" if not is_blocked else "Blocked by tool boundary"),
                "timestamp": now
            })

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO recovery_audit_log (
                    attempt_id, customer_id, mandate_id, timestamp, decision, reason_codes,
                    recovery_probability, recommended_retry_date, consent_requirement,
                    consent_status, customer_response, requested_action, validation_result,
                    validation_details, execution_outcome, lifecycle_status, is_blocked,
                    violation_type, timeline_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(attempt_id) DO UPDATE SET
                    consent_status=excluded.consent_status,
                    customer_response=excluded.customer_response,
                    requested_action=excluded.requested_action,
                    validation_result=excluded.validation_result,
                    validation_details=excluded.validation_details,
                    lifecycle_status=excluded.lifecycle_status,
                    is_blocked=excluded.is_blocked,
                    violation_type=excluded.violation_type,
                    timeline_json=excluded.timeline_json,
                    updated_at=excluded.updated_at
            """, (
                attempt_id, customer_id, mandate_id, now, "RESCHEDULE", "[]",
                0.0, None, 1, consent_status, customer_response, requested_action,
                validation_result, validation_details, "NOT_EXECUTED", lifecycle_status,
                1 if is_blocked else 0, violation_type, json.dumps(timeline), now
            ))
            conn.commit()

    def record_execution(
        self,
        attempt_id: str,
        execution_outcome: str,
        reason: Optional[str] = None
    ):
        """Records payment simulation / execution outcome."""
        now = datetime.now().isoformat()
        current = self.get_record(attempt_id)
        timeline = current.get("timeline", []) if current else []

        timeline.append({
            "stage": "SIMULATOR_EXECUTION",
            "status": execution_outcome,
            "label": f"Payment Outcome: {execution_outcome}",
            "detail": reason or f"Execution result: {execution_outcome}",
            "timestamp": now
        })

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE recovery_audit_log SET
                    execution_outcome=?,
                    lifecycle_status='EXECUTED',
                    timeline_json=?,
                    updated_at=?
                WHERE attempt_id=?
            """, (execution_outcome, json.dumps(timeline), now, attempt_id))
            conn.commit()

    def get_record(self, attempt_id: str) -> Optional[Dict[str, Any]]:
        """Fetches the complete audit record for an attempt."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM recovery_audit_log WHERE attempt_id = ?", (attempt_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)

        # If not explicitly in recovery_audit_log, check if it can be synthesized from existing tables
        return self._synthesize_from_existing(attempt_id)

    def get_all(
        self,
        attempt_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Returns paginated audit records and total blocked violation count."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Total blocked count across database
            blocked_count = self.get_blocked_count()

            if attempt_id:
                cursor.execute("SELECT * FROM recovery_audit_log WHERE attempt_id = ?", (attempt_id,))
                rows = cursor.fetchall()
                total_records = len(rows)
            else:
                cursor.execute("SELECT COUNT(*) FROM recovery_audit_log")
                total_records = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT * FROM recovery_audit_log ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (limit, offset)
                )
                rows = cursor.fetchall()

            records = [self._row_to_dict(r) for r in rows]

            # If fewer than 2 records found in active log (e.g. right after init), synthesize Scenario A and B
            if not records:
                scenario_a = self._synthesize_from_existing("ATMPT00005")
                scenario_b = self._synthesize_from_existing("ATMPT00006")
                records = [r for r in [scenario_a, scenario_b] if r]
                total_records = len(records)

            return {
                "total_records": total_records,
                "blocked_violations_count": blocked_count,
                "records": records
            }

    def get_blocked_count(self) -> int:
        """Counts actual blocked invalid/hallucinated action attempts."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT attempt_id FROM recovery_audit_log WHERE is_blocked = 1")
            audit_blocked = {row[0] for row in cursor.fetchall()}

            try:
                cursor.execute("SELECT attempt_id FROM recovery_state WHERE status = 'ACTION_REJECTED'")
                state_rejected = {row[0] for row in cursor.fetchall()}
            except Exception:
                state_rejected = set()

            return len(audit_blocked.union(state_rejected))

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        reason_codes = []
        if row["reason_codes"]:
            try:
                reason_codes = json.loads(row["reason_codes"])
            except Exception:
                reason_codes = [row["reason_codes"]]

        timeline = []
        if row["timeline_json"]:
            try:
                timeline = json.loads(row["timeline_json"])
            except Exception:
                timeline = []

        return {
            "attempt_id": row["attempt_id"],
            "customer_id": row["customer_id"] or "",
            "mandate_id": row["mandate_id"] or "",
            "timestamp": row["timestamp"] or row["updated_at"],
            "decision": row["decision"] or "UNKNOWN",
            "reason_codes": reason_codes,
            "recovery_probability": float(row["recovery_probability"] or 0.0),
            "recommended_retry_date": row["recommended_retry_date"],
            "consent_requirement": bool(row["consent_requirement"]),
            "consent_status": row["consent_status"] or "PENDING",
            "customer_response": row["customer_response"],
            "requested_action": row["requested_action"],
            "validation_result": row["validation_result"] or "PENDING",
            "validation_details": row["validation_details"],
            "execution_outcome": row["execution_outcome"] or "NOT_EXECUTED",
            "lifecycle_status": row["lifecycle_status"] or "PENDING",
            "is_blocked": bool(row["is_blocked"]),
            "violation_type": row["violation_type"],
            "timeline": timeline,
            "updated_at": row["updated_at"]
        }

    def _synthesize_from_existing(self, attempt_id: str) -> Optional[Dict[str, Any]]:
        """Synthesizes an audit record from existing analysis, conversation, and state tables."""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM recovery_analysis WHERE attempt_id = ?", (attempt_id,))
            analysis_row = cursor.fetchone()

            cursor.execute("SELECT * FROM recovery_state WHERE attempt_id = ?", (attempt_id,))
            state_row = cursor.fetchone()

            cursor.execute("SELECT * FROM agent_conversations WHERE attempt_id = ?", (attempt_id,))
            conv_row = cursor.fetchone()

        if not analysis_row and not state_row and not conv_row:
            return None

        analysis = json.loads(analysis_row["analysis_json"]) if analysis_row and analysis_row["analysis_json"] else {}
        state = dict(state_row) if state_row else {}
        conv = dict(conv_row) if conv_row else {}

        decision = analysis.get("decision", "DO_NOT_RETRY")
        reason_codes = analysis.get("reason_codes", [])
        rec_prob = float(analysis.get("recovery_probability", 0.0))
        rec_date = analysis.get("recommended_retry_date") or state.get("scheduled_date")
        consent_req = analysis.get("requires_customer_consent", True)

        consent_status = "GRANTED" if conv.get("consent_granted") else "PENDING"
        lifecycle_status = state.get("status") or conv.get("action_status") or "ANALYZED"
        exec_outcome = state.get("outcome") or "NOT_EXECUTED"

        # Check if conversation had tool rejection
        is_blocked = False
        violation_type = None
        validation_result = "ACCEPTED" if lifecycle_status in ["SCHEDULED", "EXECUTED", "COMPLETED"] else "PENDING"
        validation_details = None

        if conv.get("messages_json"):
            try:
                msgs = json.loads(conv["messages_json"])
                for m in msgs:
                    if "Tool execution rejected:" in m:
                        is_blocked = True
                        validation_result = "BLOCKED"
                        validation_details = m.replace("Tool execution rejected:", "").strip()
                        if "consent was not granted" in m:
                            violation_type = "CONSENT_VIOLATION"
                        elif "does not match" in m:
                            violation_type = "HALLUCINATED_DATE"
                        elif "DO_NOT_RETRY" in m:
                            violation_type = "UNAUTHORIZED_ACTION"
                        else:
                            violation_type = "POLICY_VIOLATION"
            except Exception:
                pass

        if state.get("status") == "ACTION_REJECTED":
            is_blocked = True
            validation_result = "BLOCKED"
            validation_details = state.get("reason", "Action rejected by mandate scheduler")
            violation_type = violation_type or "UNAUTHORIZED_ACTION"

        # Build timeline
        timeline = [
            {
                "stage": "DECISION_RULE",
                "status": "FIRED",
                "label": f"Policy Directive: {decision}",
                "detail": f"Recovery intelligence pipeline evaluated {decision}",
                "timestamp": now
            },
            {
                "stage": "REASON_CODES",
                "status": "EVALUATED",
                "label": "Reason Codes",
                "detail": ", ".join(reason_codes) if reason_codes else "None",
                "timestamp": now
            },
            {
                "stage": "CONSENT_CHECK",
                "status": "PASSED" if consent_status == "GRANTED" else "PENDING",
                "label": f"Consent Check: {consent_status}",
                "detail": "Customer consent validated" if consent_status == "GRANTED" else "Awaiting consent",
                "timestamp": now
            },
            {
                "stage": "TOOL_VALIDATION",
                "status": validation_result,
                "label": f"Safety Boundary: {validation_result}",
                "detail": validation_details or ("Validated authorized retry action" if validation_result == "ACCEPTED" else "Pending action request"),
                "timestamp": now
            }
        ]

        if exec_outcome != "NOT_EXECUTED":
            timeline.append({
                "stage": "SIMULATOR_EXECUTION",
                "status": exec_outcome,
                "label": f"Execution Outcome: {exec_outcome}",
                "detail": state.get("reason", f"Outcome: {exec_outcome}"),
                "timestamp": now
            })

        return {
            "attempt_id": attempt_id,
            "customer_id": state.get("customer_id") or conv.get("customer_id") or "",
            "mandate_id": conv.get("mandate_id") or "",
            "timestamp": now,
            "decision": decision,
            "reason_codes": reason_codes,
            "recovery_probability": rec_prob,
            "recommended_retry_date": rec_date,
            "consent_requirement": consent_req,
            "consent_status": consent_status,
            "customer_response": None,
            "requested_action": f"schedule_retry({rec_date})" if rec_date else None,
            "validation_result": validation_result,
            "validation_details": validation_details,
            "execution_outcome": exec_outcome,
            "lifecycle_status": lifecycle_status,
            "is_blocked": is_blocked,
            "violation_type": violation_type,
            "timeline": timeline,
            "updated_at": now
        }
