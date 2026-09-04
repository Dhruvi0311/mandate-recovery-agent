import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import pandas as pd

from src.features.feature_pipeline import FeaturePipeline
from src.prediction.prediction_pipeline import PredictionPipeline
from src.decision.policy_engine import DecisionEngine
from src.decision.decision_models import DecisionInput, PolicyConfig
from src.simulator.outcome_service import OutcomeService
from src.simulator.payment_simulator import PaymentSimulator

logger = logging.getLogger("batch_evaluator")

DEFAULT_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
DEFAULT_MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "prediction", "models"))
DEFAULT_REPORT_PATH = os.path.join(DEFAULT_DATA_DIR, "batch_recovery_report.json")
DEFAULT_BATCH_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "db", "batch_evaluation.db"))

BOUNCE_FEE_ASSUMPTION_TEXT = "₹500 bank bounce charge per failed attempt as specified in PRD.md"
DEFAULT_BOUNCE_FEE = 500.0

class BatchEvaluator:
    """
    Evaluates the Intelligent Recovery Strategy vs. Naive +2-Day Baseline across all failed attempts.
    Reuses existing FeaturePipeline, PredictionPipeline, DecisionEngine, and PaymentSimulator.
    Enforces ground-truth isolation and avoids mutating live demo application state.
    """

    def __init__(
        self,
        data_dir: str = DEFAULT_DATA_DIR,
        model_dir: str = DEFAULT_MODEL_DIR,
        report_path: str = DEFAULT_REPORT_PATH,
        batch_db_path: str = DEFAULT_BATCH_DB,
        fee_per_retry: float = DEFAULT_BOUNCE_FEE,
    ):
        self.data_dir = data_dir
        self.model_dir = model_dir
        self.report_path = report_path
        self.batch_db_path = batch_db_path
        self.fee_per_retry = fee_per_retry

        # Pipelines
        self.feature_pipeline = FeaturePipeline(data_dir=self.data_dir)
        self.prediction_pipeline = PredictionPipeline(data_dir=self.data_dir, model_dir=self.model_dir)
        self.decision_engine = DecisionEngine(config=PolicyConfig())

        # Isolated OutcomeService to guarantee no mutation of live app_state.db
        self.outcome_service = OutcomeService(db_path=self.batch_db_path)
        self.simulator = PaymentSimulator(
            outcome_service=self.outcome_service,
            data_path=os.path.join(self.data_dir, "mandate_attempts.csv")
        )

    def load_or_compute(self, force_recompute: bool = False) -> Dict[str, Any]:
        """
        Loads the precomputed batch report if available and not forced,
        otherwise runs the batch evaluation pipeline and persists the artifact.
        """
        if not force_recompute and os.path.exists(self.report_path):
            try:
                with open(self.report_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "intelligent_strategy" in data and "naive_baseline" in data:
                        return data
            except Exception as e:
                logger.warning(f"Failed to read existing batch report from {self.report_path}: {e}. Recomputing.")

        return self.compute_batch_report()

    def compute_batch_report(self) -> Dict[str, Any]:
        """
        Runs the full batch evaluation across all failed attempts in mandate_attempts.csv.
        """
        attempts_df = self.feature_pipeline.attempts_df
        failed_df = attempts_df[attempts_df["status"] == "FAILED"].copy()

        total_failed_attempts = len(failed_df)
        total_amount = float(failed_df["amount_required"].sum())

        intelligent_recovered_amount = 0.0
        intelligent_recovered_count = 0
        intelligent_retries_attempted = 0

        naive_recovered_amount = 0.0
        naive_recovered_count = 0
        naive_retries_attempted = total_failed_attempts  # Naive baseline blindly retries every failed attempt

        do_not_retry_count = 0
        decision_breakdown: Dict[str, int] = {}

        for _, row in failed_df.iterrows():
            attempt_id = str(row["attempt_id"])
            customer_id = str(row["customer_id"])
            amount_required = float(row["amount_required"])
            attempt_date_raw = row["attempt_date"]
            attempt_date_str = str(attempt_date_raw.date()) if isinstance(attempt_date_raw, pd.Timestamp) else str(attempt_date_raw)[:10]

            # 1. Feature Engine (Strict point-in-time features, no leakage)
            fv = self.feature_pipeline.generate_features_for_inference(attempt_id)

            # 2. Prediction Engine
            pred_recovery = self.prediction_pipeline.predict_recovery(attempt_id)
            recovery_prob = float(pred_recovery["recovery_probability"])

            retry_window = self.prediction_pipeline.predict_retry_window(attempt_id)
            recommended_date = retry_window.get("recommended_retry_date")

            # 3. Decision Engine
            mandate_status = str(fv.get("mandate_status", "ACTIVE"))
            current_attempt_num = int(fv.get("current_attempt_number", 1))
            prior_failed_attempts = int(fv.get("num_prior_failed_attempts", 0))
            failure_reason = str(fv.get("failure_reason", "INSUFFICIENT_FUNDS"))

            decision_input = DecisionInput(
                attempt_id=attempt_id,
                recovery_probability=recovery_prob,
                recommended_retry_date=recommended_date or "",
                failure_reason=failure_reason,
                mandate_status=mandate_status,
                current_attempt_number=current_attempt_num,
                previous_failed_attempts=prior_failed_attempts
            )
            decision_output = self.decision_engine.evaluate(decision_input)
            decision = decision_output.decision
            decision_breakdown[decision] = decision_breakdown.get(decision, 0) + 1

            if decision == "DO_NOT_RETRY":
                do_not_retry_count += 1

            # 4. Strategy A: Intelligent Recovery Simulation
            # Only retry paths (RESCHEDULE or RETRY_NOW) are scheduled and evaluated
            if decision == "RESCHEDULE" and decision_output.recommended_retry_date:
                intelligent_retries_attempted += 1
                scheduled_date = decision_output.recommended_retry_date
                self.outcome_service.update_state(
                    attempt_id=attempt_id,
                    customer_id=customer_id,
                    status="SCHEDULED",
                    scheduled_date=scheduled_date
                )
                sim_res = self.simulator.execute_scheduled_retry(attempt_id)
                if sim_res.get("result") == "SUCCESS":
                    intelligent_recovered_amount += amount_required
                    intelligent_recovered_count += 1
            elif decision == "RETRY_NOW":
                intelligent_retries_attempted += 1
                # In the date-only canonical dataset, next valid clearing window is modeled at attempt_date + 1 day
                attempt_dt = pd.to_datetime(attempt_date_str)
                scheduled_date = str((attempt_dt + pd.Timedelta(days=1)).date())
                self.outcome_service.update_state(
                    attempt_id=attempt_id,
                    customer_id=customer_id,
                    status="SCHEDULED",
                    scheduled_date=scheduled_date
                )
                sim_res = self.simulator.execute_scheduled_retry(attempt_id)
                if sim_res.get("result") == "SUCCESS":
                    intelligent_recovered_amount += amount_required
                    intelligent_recovered_count += 1

            # 5. Strategy B: Naive +2-Day Baseline Simulation
            # Fixed attempt_date + 2 days, evaluated through the exact same simulator logic
            attempt_dt = pd.to_datetime(attempt_date_str)
            naive_date_str = str((attempt_dt + pd.Timedelta(days=2)).date())
            self.outcome_service.update_state(
                attempt_id=attempt_id,
                customer_id=customer_id,
                status="SCHEDULED",
                scheduled_date=naive_date_str
            )
            naive_sim_res = self.simulator.execute_scheduled_retry(attempt_id)
            if naive_sim_res.get("result") == "SUCCESS":
                naive_recovered_amount += amount_required
                naive_recovered_count += 1

        # Calculate comparative metrics
        intelligent_recovery_rate = round(intelligent_recovered_count / total_failed_attempts, 4) if total_failed_attempts else 0.0
        naive_recovery_rate = round(naive_recovered_count / total_failed_attempts, 4) if total_failed_attempts else 0.0
        incremental_recovery = round(intelligent_recovered_amount - naive_recovered_amount, 2)
        retries_avoided = total_failed_attempts - intelligent_retries_attempted

        savings_from_retries_avoided = round(retries_avoided * self.fee_per_retry, 2)
        savings_from_do_not_retry = round(do_not_retry_count * self.fee_per_retry, 2)

        report = {
            "total_failed_attempts": total_failed_attempts,
            "total_amount": round(total_amount, 2),
            "intelligent_strategy": {
                "amount_recovered": round(intelligent_recovered_amount, 2),
                "recovery_rate": intelligent_recovery_rate,
                "recovered_count": intelligent_recovered_count,
                "retries_attempted": intelligent_retries_attempted
            },
            "naive_baseline": {
                "amount_recovered": round(naive_recovered_amount, 2),
                "recovery_rate": naive_recovery_rate,
                "recovered_count": naive_recovered_count,
                "retries_attempted": naive_retries_attempted
            },
            "incremental_recovery": incremental_recovery,
            "retries_avoided": retries_avoided,
            "do_not_retry_count": do_not_retry_count,
            "bounce_fee": {
                "fee_per_retry": self.fee_per_retry,
                "fee_assumption": BOUNCE_FEE_ASSUMPTION_TEXT,
                "savings_from_retries_avoided": savings_from_retries_avoided,
                "savings_from_do_not_retry": savings_from_do_not_retry
            },
            "decision_breakdown": decision_breakdown,
            "generated_at": datetime.now().isoformat()
        }

        # Persist report artifact
        os.makedirs(os.path.dirname(self.report_path), exist_ok=True)
        with open(self.report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        return report
