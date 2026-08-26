# Data Provenance Investigation

## 1. Current Dataset Files and Their Apparent Source
The workspace currently contains the following 6 CSV files located in the `data/` directory:
- `consents.csv`
- `customers.csv`
- `mandate_attempts.csv`
- `mandates.csv`
- `recovery_actions.csv`
- `transactions.csv`

**Apparent Source (Confirmed Fact):** The origin of these specific files is currently **unknown** and external to this workspace. The only generation script provided (`generate_synthetic_data.py`) does not match the schemas, scale, or output paths of the current CSVs, indicating these files were generated, enriched, or modified by an undocumented external process.

## 2. What `generate_synthetic_data.py` Currently Generates
A detailed inspection of the Python generator script reveals it produces exactly 4 datasets:
- `customers.csv`
- `transactions.csv`
- `mandates.csv`
- `mandate_attempts.csv`

**Key configuration in the script:**
- Number of simulated customers: `120`
- Output directories: Linux-style paths (`/mnt/user-data/outputs/`) rather than the local Windows directory (`data/`).

## 3. Differences Between Generator Output Schema and Current CSV Schema
The current CSV dataset diverges significantly from the script's output:
- **Missing Tables:** `consents.csv` and `recovery_actions.csv` are entirely absent from the generation script.
- **Customer Scale:** `customers.csv` contains 168 rows, while the script is hardcoded to generate exactly 120.
- **Schema Mismatches:**
  - `customers.csv`: The generator creates `income_type`. The CSV instead contains `behavior_type` and `scenario_tag`.
  - `mandate_attempts.csv`: The CSV contains critical ML fields (`ground_truth_retry_date`, `ground_truth_recoverable`) that are never calculated or outputted by the generator script.

## 4. Evidence for How Additional Fields/Datasets May Have Been Produced
An exhaustive search of the workspace (including hidden files, `.git` history, and `.agents` configurations) yielded **no evidence** of how the enrichment occurred. 

**Confirmed Facts:**
- There are no Jupyter notebooks (`*.ipynb`), bash scripts, or secondary Python scripts in the workspace.
- The directory is not a Git repository, meaning we cannot inspect commit history to find previous data transformation code.
- No local knowledge items (KI) exist to explain the data provenance.

**Hypothesis:**
The CSVs were likely enriched in a separate data science environment (e.g., a Jupyter Notebook or a data pipeline not checked into this workspace) to add the ground-truth ML labels, scenario tags, and recovery actions datasets, and then manually copied into this repository.

## 5. Canonical Dataset for the MVP
**The current CSV dataset MUST be treated as the canonical dataset for the MVP.** 

Despite the lack of generation scripts, the CSV files contain the necessary labels (`ground_truth_recoverable`), complex edge cases (`scenario_tag`), and supporting tables (`consents.csv`, `recovery_actions.csv`) required to build out the ML and agent functionality. Relying on the current `generate_synthetic_data.py` would result in a dataset missing critical features needed for the MVP.

## 6. Should the Generator Be Updated Later?
**Yes.** In a production environment, relying on orphaned CSVs without a reproducible generation pipeline introduces significant technical debt and prevents easily simulating new scenarios or fixing bugs in the synthetic data.

## 7. Recommended Approach for Reproducibility
To achieve data reproducibility, the team should:
1. **Reverse-Engineer the Enrichment (Short Term):** Write a new Python script (`enrich_data.py`) that explicitly takes the output of the current `generate_synthetic_data.py` and applies the transformations to create `behavior_type`, `scenario_tag`, `ground_truth_recoverable`, `consents.csv`, and `recovery_actions.csv`.
2. **Refactor the Generator (Long Term):** Rewrite `generate_synthetic_data.py` completely so it natively generates all 6 datasets with the enriched schemas directly, parameterizing the output paths so it works seamlessly on Windows and Linux alike.
