import os
import json
import sqlite3
import unittest
from fastapi.testclient import TestClient

from src.api.main import app
from src.evaluation.batch_evaluator import BatchEvaluator, DEFAULT_REPORT_PATH
from src.decision.decision_models import DecisionInput
from src.api.dependencies import get_db_path

class TestBatchReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.evaluator = BatchEvaluator()

    def test_batch_report_endpoint_status_and_schema(self):
        """Validates that GET /api/batch-report returns 200 and matches the expected schema."""
        response = self.client.get("/api/batch-report")
        self.assertEqual(response.status_code, 200, f"Expected 200, got: {response.text}")
        data = response.json()

        required_keys = [
            "total_failed_attempts",
            "total_amount",
            "intelligent_strategy",
            "naive_baseline",
            "incremental_recovery",
            "retries_avoided",
            "do_not_retry_count",
            "bounce_fee",
            "decision_breakdown",
            "generated_at"
        ]
        for k in required_keys:
            self.assertIn(k, data, f"Key '{k}' missing from batch report response")

        # Sub-structures
        self.assertIn("amount_recovered", data["intelligent_strategy"])
        self.assertIn("recovery_rate", data["intelligent_strategy"])
        self.assertIn("amount_recovered", data["naive_baseline"])
        self.assertIn("recovery_rate", data["naive_baseline"])

        self.assertIn("fee_per_retry", data["bounce_fee"])
        self.assertIn("fee_assumption", data["bounce_fee"])
        self.assertIn("savings_from_retries_avoided", data["bounce_fee"])
        self.assertIn("savings_from_do_not_retry", data["bounce_fee"])

    def test_intelligent_vs_naive_calculations(self):
        """Validates calculations for intelligent strategy vs naive baseline."""
        response = self.client.get("/api/batch-report")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        total_failed = data["total_failed_attempts"]
        total_amount = data["total_amount"]
        intel = data["intelligent_strategy"]
        naive = data["naive_baseline"]
        inc_rec = data["incremental_recovery"]

        self.assertGreater(total_failed, 0)
        self.assertGreater(total_amount, 0)

        # Expected recovery rate = recovered_count / total_failed_attempts
        expected_intel_rate = round(intel["recovered_count"] / total_failed, 4)
        expected_naive_rate = round(naive["recovered_count"] / total_failed, 4)
        self.assertAlmostEqual(intel["recovery_rate"], expected_intel_rate, places=3)
        self.assertAlmostEqual(naive["recovery_rate"], expected_naive_rate, places=3)

        # Incremental recovery = intel.amount_recovered - naive.amount_recovered
        expected_incremental = round(intel["amount_recovered"] - naive["amount_recovered"], 2)
        self.assertAlmostEqual(inc_rec, expected_incremental, places=2)

    def test_retry_avoidance_and_bounce_fee_savings(self):
        """Validates retries avoided, DO_NOT_RETRY count, and documented bounce fee calculation."""
        response = self.client.get("/api/batch-report")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        total_failed = data["total_failed_attempts"]
        intel_retries = data["intelligent_strategy"]["retries_attempted"]
        retries_avoided = data["retries_avoided"]
        do_not_retry = data["do_not_retry_count"]
        fee_info = data["bounce_fee"]

        # Retries avoided = total failed - retries attempted
        self.assertEqual(retries_avoided, total_failed - intel_retries)
        self.assertGreater(retries_avoided, 0)
        self.assertGreater(do_not_retry, 0)

        # Configured fee is 500
        self.assertEqual(fee_info["fee_per_retry"], 500.0)
        self.assertIn("PRD.md", fee_info["fee_assumption"])
        self.assertIn("500", fee_info["fee_assumption"])

        # Savings = count * fee
        self.assertEqual(fee_info["savings_from_retries_avoided"], round(retries_avoided * 500.0, 2))
        self.assertEqual(fee_info["savings_from_do_not_retry"], round(do_not_retry * 500.0, 2))

    def test_ground_truth_isolation(self):
        """Verifies that model feature vectors exclude ground-truth labels during batch evaluation."""
        prohibited_keys = [
            "ground_truth_recoverable",
            "ground_truth_retry_date",
            "recovery_probability",
            "predicted_retry_date",
            "recommended_action",
            "actual_retry_result",
            "customer_response",
            "scenario_tag"
        ]
        # Inspect feature vector for a failed attempt
        fv = self.evaluator.feature_pipeline.generate_features_for_inference("ATMPT00005")
        for key in prohibited_keys:
            self.assertNotIn(key, fv, f"Prohibited ground truth key '{key}' leaked into feature vector!")

    def test_persistence_and_queryability(self):
        """Validates that report is persisted to disk and fast to query."""
        report = self.evaluator.load_or_compute(force_recompute=False)
        self.assertIsInstance(report, dict)
        self.assertTrue(os.path.exists(DEFAULT_REPORT_PATH), f"Report file {DEFAULT_REPORT_PATH} not found")

        # Loading again without force should load directly from disk
        report2 = self.evaluator.load_or_compute(force_recompute=False)
        self.assertEqual(report["total_failed_attempts"], report2["total_failed_attempts"])

    def test_live_state_non_corruption(self):
        """Verifies batch evaluation does not overwrite or corrupt live interactive SQLite state."""
        live_db = get_db_path()
        with sqlite3.connect(live_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM recovery_state")
            count_before = cursor.fetchone()[0]

        # Call batch report endpoint
        response = self.client.get("/api/batch-report")
        self.assertEqual(response.status_code, 200)

        with sqlite3.connect(live_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM recovery_state")
            count_after = cursor.fetchone()[0]

        self.assertEqual(count_before, count_after, "Batch evaluation modified the live recovery_state table!")

    def test_retry_now_recoverable_technical_failure_succeeds_at_t_plus_1(self):
        """(A & B) A recoverable technical failure with GT=T+1 succeeds under RETRY_NOW (T+1) and under naive (T+2)."""
        attempt_id = "ATMPT00015"
        # ATMPT00015: attempt_date = 2026-03-04, GT = 2026-03-05, recoverable = True
        fv = self.evaluator.feature_pipeline.generate_features_for_inference(attempt_id)
        self.assertEqual(fv.get("failure_reason"), "TECHNICAL_FAILURE")

        # Intelligent evaluation
        dec_in = DecisionInput(
            attempt_id=attempt_id,
            recovery_probability=0.75,
            recommended_retry_date="",
            failure_reason="TECHNICAL_FAILURE",
            mandate_status=str(fv.get("mandate_status", "ACTIVE")),
            current_attempt_number=1,
            previous_failed_attempts=0
        )
        dec_out = self.evaluator.decision_engine.evaluate(dec_in)
        self.assertEqual(dec_out.decision, "RETRY_NOW")

        # RETRY_NOW scheduled at T+1 (2026-03-05)
        self.evaluator.outcome_service.update_state(
            attempt_id=attempt_id,
            customer_id="CUST0002",
            status="SCHEDULED",
            scheduled_date="2026-03-05"
        )
        res_intel = self.evaluator.simulator.execute_scheduled_retry(attempt_id)
        self.assertEqual(res_intel["result"], "SUCCESS")

        # Naive scheduled at T+2 (2026-03-06)
        self.evaluator.outcome_service.update_state(
            attempt_id=attempt_id,
            customer_id="CUST0002",
            status="SCHEDULED",
            scheduled_date="2026-03-06"
        )
        res_naive = self.evaluator.simulator.execute_scheduled_retry(attempt_id)
        self.assertEqual(res_naive["result"], "SUCCESS")

    def test_retry_now_unrecoverable_technical_failure_remains_failure(self):
        """(C) An unrecoverable technical failure (ATMPT01090) remains a failure under simulation."""
        attempt_id = "ATMPT01090"
        self.evaluator.outcome_service.update_state(
            attempt_id=attempt_id,
            customer_id="CUST0086",
            status="SCHEDULED",
            scheduled_date="2026-05-13"
        )
        res = self.evaluator.simulator.execute_scheduled_retry(attempt_id)
        self.assertEqual(res["result"], "FAILURE")
        self.assertIn("Customer funds remained insufficient", res["reason"])

    def test_reschedule_behavior_unchanged(self):
        """(D & E) Confirms Scenario A (ATMPT00005) evaluates to RESCHEDULE and Scenario B (ATMPT00006) to DO_NOT_RETRY."""
        # Scenario A
        pred_a = self.evaluator.prediction_pipeline.predict_recovery("ATMPT00005")
        window_a = self.evaluator.prediction_pipeline.predict_retry_window("ATMPT00005")
        fv_a = self.evaluator.feature_pipeline.generate_features_for_inference("ATMPT00005")

        dec_a = self.evaluator.decision_engine.evaluate(DecisionInput(
            attempt_id="ATMPT00005",
            recovery_probability=float(pred_a["recovery_probability"]),
            recommended_retry_date=window_a["recommended_retry_date"],
            failure_reason=str(fv_a.get("failure_reason")),
            mandate_status=str(fv_a.get("mandate_status", "ACTIVE")),
            current_attempt_number=int(fv_a.get("current_attempt_number", 1)),
            previous_failed_attempts=int(fv_a.get("num_prior_failed_attempts", 0))
        ))
        self.assertEqual(dec_a.decision, "RESCHEDULE")
        self.assertEqual(dec_a.recommended_retry_date, "2026-07-21")

        # Scenario B
        pred_b = self.evaluator.prediction_pipeline.predict_recovery("ATMPT00006")
        fv_b = self.evaluator.feature_pipeline.generate_features_for_inference("ATMPT00006")
        dec_b = self.evaluator.decision_engine.evaluate(DecisionInput(
            attempt_id="ATMPT00006",
            recovery_probability=float(pred_b["recovery_probability"]),
            recommended_retry_date="",
            failure_reason=str(fv_b.get("failure_reason")),
            mandate_status=str(fv_b.get("mandate_status", "ACTIVE")),
            current_attempt_number=int(fv_b.get("current_attempt_number", 1)),
            previous_failed_attempts=int(fv_b.get("num_prior_failed_attempts", 0))
        ))
        self.assertEqual(dec_b.decision, "DO_NOT_RETRY")
        self.assertIsNone(dec_b.recommended_retry_date)

    def test_rogue_agent_protection_unchanged(self):
        """(F) Validates that rogue schedule_retry with hallucinated date is blocked by the tool boundary."""
        res = self.client.post("/api/agent/ATMPT00005/simulate-rogue")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["validation_result"], "BLOCKED")
        self.assertEqual(data["violation_type"], "HALLUCINATED_DATE")

    def test_no_ground_truth_fields_in_inference_features_or_inputs(self):
        """(G) Strict verification that no ground truth columns leak into feature generation."""
        prohibited = [
            "ground_truth_recoverable",
            "ground_truth_retry_date",
            "recovery_probability",
            "predicted_retry_date",
            "recommended_action",
            "actual_retry_result",
            "customer_response",
            "scenario_tag"
        ]
        # Test across both technical and financial attempts
        for aid in ["ATMPT00005", "ATMPT00015", "ATMPT01090"]:
            fv = self.evaluator.feature_pipeline.generate_features_for_inference(aid)
            for p in prohibited:
                self.assertNotIn(p, fv, f"Prohibited key '{p}' leaked in attempt {aid}")

if __name__ == "__main__":
    unittest.main()

