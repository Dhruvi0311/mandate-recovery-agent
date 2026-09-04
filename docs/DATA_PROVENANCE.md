# Data Provenance & Canonical Dataset Reconciliation

## 1. Executive Summary

> **"The canonical CSVs were the given hackathon dataset; we treated them as ground truth and audited them for leakage — full audit in docs/DATA_AUDIT.md."**

The final Mandate Recovery Agent system relies strictly and exclusively on the six canonical CSV files located in the `data/` directory:
1. `data/customers.csv`
2. `data/transactions.csv`
3. `data/mandates.csv`
4. `data/mandate_attempts.csv`
5. `data/consents.csv`
6. `data/recovery_actions.csv`

---

## 2. Canonical Dataset Treatment & Principles

1. **Authoritative Input & Ground Truth**: The six canonical CSVs are the authoritative input dataset used by the final system for feature extraction, ML training, Decision Engine policies, customer consent verification, simulator execution, and batch recovery impact reporting.
2. **Pre-Pipeline Audit for Leakage**: Before building the Feature Engine and Machine Learning prediction pipelines, we performed an exhaustive leakage and data-contract audit (detailed in [docs/DATA_AUDIT.md](DATA_AUDIT.md)).
3. **Evaluation Labels Isolation**:
   - `ground_truth_recoverable` and `ground_truth_retry_date` (in `data/mandate_attempts.csv`) are strictly evaluation labels and simulation ground truth.
   - They are **never** used as input features for model training or inference. The prediction models use strictly point-in-time features computed from transactions occurring on or before `attempt_date`.
4. **Role of `recovery_actions.csv`**:
   - `data/recovery_actions.csv` contains prior/reference outputs and legacy heuristic benchmarks.
   - It is **not** used as ML training features, inference inputs, or ground truth. The system computes its own features, predictions, and decisions dynamically.

---

## 3. Status of `generate_synthetic_data.py`

The workspace contains an artifact script named `generate_synthetic_data.py`. 

- **Older / Incomplete Prototype**: `generate_synthetic_data.py` is an older, incomplete prototype script. It writes to Linux-specific paths (`/mnt/user-data/outputs/`) and only defines 4 tables for 120 customers.
- **Does NOT Reproduce Canonical Data**: The script does **not** reproduce the current canonical six-file dataset (which contains 168 customers, 1,746 attempts, 12,870 transactions, rich golden scenario tags, dual consents, and ground-truth simulation labels).
- **Not Part of Final Pipeline**: Because the canonical CSVs were the given hackathon dataset and serve as authoritative ground truth, `generate_synthetic_data.py` is **not part of the final data-generation pipeline** and does **not** need to be rewritten, executed, or modified for the final submission.

---

## 4. Documentation Map

For complete specifications and architectural contracts, refer to:
- [docs/DATA_AUDIT.md](DATA_AUDIT.md): Comprehensive data audit, ER diagrams, foreign key integrity, and leakage analysis.
- [docs/DATA_PROVENANCE.md](DATA_PROVENANCE.md): Provenance reconciliation, authoritative dataset definition, and generator status.
- [docs/DATA_CONTRACT.md](DATA_CONTRACT.md): Formal entity schemas, temporal constraints, and API boundaries.
