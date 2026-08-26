import unittest
import pandas as pd
import os
from src.consent.consent_service import ConsentService
from src.simulator.outcome_service import OutcomeService
from src.simulator.mandate_scheduler import MandateScheduler, SchedulerException
from src.simulator.payment_simulator import PaymentSimulator

class TestSimulator(unittest.TestCase):
    def setUp(self):
        # Create temp files
        self.mock_consents = "test_consents_sim.csv"
        pd.DataFrame([
            {"customer_id": "C001", "consent_id": "CON1", "status": "ACTIVE", "data_scope": "TRANSACTIONS", "expiry_date": "2099-01-01"},
            {"customer_id": "C002", "consent_id": "CON2", "status": "REVOKED", "data_scope": "TRANSACTIONS", "expiry_date": "2099-01-01"}
        ]).to_csv(self.mock_consents, index=False)
        
        self.mock_attempts = "test_attempts_sim.csv"
        pd.DataFrame([
            {"attempt_id": "A1", "ground_truth_recoverable": True, "ground_truth_retry_date": "2026-07-01"},
            {"attempt_id": "A2", "ground_truth_recoverable": False, "ground_truth_retry_date": "2026-07-01"},
            {"attempt_id": "A3", "ground_truth_recoverable": True, "ground_truth_retry_date": "2026-07-05"} # Needs wait
        ]).to_csv(self.mock_attempts, index=False)
        
        self.mock_db = "test_state.db"
        
        self.consent_service = ConsentService(data_path=self.mock_consents)
        self.outcome_service = OutcomeService(db_path=self.mock_db)
        self.scheduler = MandateScheduler(self.consent_service, self.outcome_service)
        self.simulator = PaymentSimulator(self.outcome_service, data_path=self.mock_attempts)

    def tearDown(self):
        for f in [self.mock_consents, self.mock_attempts, self.mock_db]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

    def test_successful_schedule_and_execution(self):
        # 1. Schedule
        decision_context = {"decision": "RESCHEDULE", "recommended_retry_date": "2026-07-01"}
        self.scheduler.schedule_retry("A1", "C001", "2026-07-01", decision_context, action_consent_granted=True)
        
        state = self.outcome_service.get_state("A1")
        self.assertEqual(state["status"], "SCHEDULED")
        
        # 2. Execute 
        res = self.simulator.execute_scheduled_retry("A1")
        self.assertEqual(res["result"], "SUCCESS")
        
        state = self.outcome_service.get_state("A1")
        self.assertEqual(state["status"], "EXECUTED")
        self.assertEqual(state["outcome"], "SUCCESS")

    def test_failed_execution_insufficient_funds(self):
        # Attempt A2 is not recoverable
        decision_context = {"decision": "RESCHEDULE", "recommended_retry_date": "2026-07-01"}
        self.scheduler.schedule_retry("A2", "C001", "2026-07-01", decision_context, True)
        
        res = self.simulator.execute_scheduled_retry("A2")
        self.assertEqual(res["result"], "FAILURE")

    def test_failed_execution_too_early(self):
        # Attempt A3 funds aren't available until 07-05, we retry on 07-01
        decision_context = {"decision": "RESCHEDULE", "recommended_retry_date": "2026-07-01"}
        self.scheduler.schedule_retry("A3", "C001", "2026-07-01", decision_context, True)
        
        res = self.simulator.execute_scheduled_retry("A3")
        self.assertEqual(res["result"], "FAILURE")
        self.assertEqual(res["reason"], "Retry occurred too early before funds were available.")

    def test_schedule_fails_missing_action_consent(self):
        decision_context = {"decision": "RESCHEDULE", "recommended_retry_date": "2026-07-01"}
        with self.assertRaisesRegex(SchedulerException, "Customer did not consent"):
            self.scheduler.schedule_retry("A1", "C001", "2026-07-01", decision_context, action_consent_granted=False)

    def test_schedule_fails_invalid_data_consent(self):
        decision_context = {"decision": "RESCHEDULE", "recommended_retry_date": "2026-07-01"}
        with self.assertRaisesRegex(SchedulerException, "Invalid Data Consent"):
            self.scheduler.schedule_retry("A1", "C002", "2026-07-01", decision_context, action_consent_granted=True)
            
    def test_schedule_fails_date_mismatch(self):
        decision_context = {"decision": "RESCHEDULE", "recommended_retry_date": "2026-07-01"}
        with self.assertRaisesRegex(SchedulerException, "does not match authorized date"):
            self.scheduler.schedule_retry("A1", "C001", "2026-07-02", decision_context, True) # Hallucinated 07-02
            
    def test_schedule_fails_unauthorized_decision(self):
        decision_context = {"decision": "DO_NOT_RETRY", "recommended_retry_date": None}
        with self.assertRaisesRegex(SchedulerException, "blocked retry scheduling"):
            self.scheduler.schedule_retry("A1", "C001", "2026-07-01", decision_context, True)

if __name__ == '__main__':
    unittest.main()
