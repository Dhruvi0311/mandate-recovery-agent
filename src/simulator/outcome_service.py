import sqlite3
import os
from typing import Dict, Any

class OutcomeService:
    def __init__(self, db_path: str = "db/app_state.db"):
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        dirname = os.path.dirname(self.db_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
            
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recovery_state (
                    attempt_id TEXT PRIMARY KEY,
                    customer_id TEXT,
                    status TEXT,
                    scheduled_date TEXT,
                    execution_time TEXT,
                    outcome TEXT,
                    reason TEXT
                )
            """)
            conn.commit()
            
    def update_state(self, attempt_id: str, customer_id: str, status: str, 
                     scheduled_date: str = None, execution_time: str = None, 
                     outcome: str = None, reason: str = None):
        """Upserts the lifecycle state for a mandate attempt into SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO recovery_state (attempt_id, customer_id, status, scheduled_date, execution_time, outcome, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(attempt_id) DO UPDATE SET
                    status=excluded.status,
                    scheduled_date=COALESCE(excluded.scheduled_date, recovery_state.scheduled_date),
                    execution_time=COALESCE(excluded.execution_time, recovery_state.execution_time),
                    outcome=COALESCE(excluded.outcome, recovery_state.outcome),
                    reason=COALESCE(excluded.reason, recovery_state.reason)
            """, (attempt_id, customer_id, status, scheduled_date, execution_time, outcome, reason))
            conn.commit()

    def get_state(self, attempt_id: str) -> Dict[str, Any]:
        """Retrieves the current state of an attempt."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM recovery_state WHERE attempt_id = ?", (attempt_id,))
            row = cursor.fetchone()
            return dict(row) if row else {}
