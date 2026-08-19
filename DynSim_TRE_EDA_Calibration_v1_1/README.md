# DynSim TRE EDA + Calibration v1.3

This is the lean TRE-side workflow for DynSim.

It deliberately follows the same pattern as the earlier six-table TRE EDA:

```text
TRE source tables
      ↓
EDA / structural discovery
      ↓
statistical + temporal + relationship findings
      ↓
machine-readable aggregate profile
      ↓
TRE disclosure review
      ↓
approved aggregate metadata
      ↓
DynSim outside the TRE
```

The important change is that the EDA findings are now captured as structured
aggregate outputs instead of existing only as terminal print-outs.

## No hard-coded findings

The repository does **not** contain the observed row counts, patient counts,
distributions, date ranges, overlap counts, utilisation rates or other
statistical findings from the TRE.

Source tables are discovered at runtime. Candidate keys and cross-table patient
linkage are resolved from the data itself.

The code contains only generic EDA logic and structural concepts such as
"spell/episode-like", "ED-like" and "pathway-like" table detection.

## What the EDA captures

### Common structure
- raw rows and columns
- exact duplicates
- fully blank rows
- schema, dtype, missingness and cardinality
- resolved patient/event keys
- structured key-integrity/cardinality QA

### Pathway-like tables
- referral/row burden per patient
- full count distribution
- repeat-referral gaps
- referral → first event timing
- first → last timing
- chronology QA

### Inpatient-like tables
- spell nesting within patient
- episodes per spell
- spells per patient
- full event-count distributions
- spell-level LOS
- admission/discharge and episode chronology QA
- numbered clinical-slot occupancy

### ED-like tables
- patient/event composite-key QA
- attendance-level deduplicated view
- attendances per patient
- full attendance-count distribution
- arrival/departure timing
- repeat-attendance gaps
- numbered clinical-slot occupancy

### Calibration used across tables
- numeric distribution shape: mean, SD, variance, skewness, kurtosis and quantiles
- categorical distributions
- top-N + `__OTHER__` for high-cardinality categorical/code fields
- datetime coverage
- monthly/yearly/day-of-week/hour seasonality
- within-patient consistency
- row/pairwise missingness structure
- Pearson/Spearman numeric dependencies
- Cramér's V categorical dependencies
- strongest categorical joint/conditional distributions
- cross-table patient overlap and coverage
- generic anomaly candidates for isolated date years and extreme numeric values

## Run inside the TRE

```bash
python scripts/run_tre_eda_calibration.py \
  --input /project/readonly \
  --output metadata_profiles/internal
```

Then:

```bash
python scripts/validate_profile.py \
  --profile metadata_profiles/internal
```

Review the outputs against the findings from the earlier TRE EDA before
preparing anything for egress.

## Aggregate outputs

The workflow writes:

```text
eda_table_inventory.csv
eda_schema.csv
eda_keys.csv
eda_key_qa.csv
eda_anomaly_candidates.csv
eda_count_summaries.csv
eda_count_distributions.csv
eda_numeric.csv
eda_categorical.csv
eda_dates.csv
eda_intervals.csv
eda_temporal_qa.csv
eda_slot_occupancy.csv
eda_seasonality.csv
eda_within_patient_consistency.csv
eda_row_missingness.csv
eda_missingness_pairs.csv
eda_missingness_patterns.csv
eda_numeric_correlations.csv
eda_categorical_associations.csv
eda_categorical_joint.csv
eda_cross_table_relationships.csv
portable_metadata.json
manifest.json
```

`portable_metadata.json` is the consolidated DynSim calibration contract.

## Egress

Do not use a hard-coded disclosure threshold.

After the TRE output-checking team confirms the applicable rules:

```bash
python scripts/prepare_egress.py \
  --internal metadata_profiles/internal \
  --export metadata_profiles/export \
  --min-cell-count <APPROVED_THRESHOLD> \
  --round-base <APPROVED_ROUNDING_BASE>
```

The output ZIP remains an egress candidate and must follow the approved TRE
disclosure process.

## Outside the TRE

DynSim should consume the approved `portable_metadata.json`, generate
low-fidelity synthetic tables with comparable structure and calibration, and
support development of the ingestion/cleaning/preprocessing/analysis workflow.

The completed workflow can then be translated back into the TRE with the same
expected table grain, keys, temporal structures and relationships.


## Anomaly capture

The workflow records aggregate data-quality structure rather than relying on a
project-specific anomaly list:

- per-column missingness
- row-level missingness burden
- pairwise joint missingness
- common missingness patterns
- exact duplicate rows and fully blank rows
- key-integrity/cardinality findings
- date-parse failures and chronology violations
- negative and zero interval counts
- isolated early/late calendar years
- extreme numeric values using a robust-IQR rule
- within-patient inconsistencies
- cross-table linkage/coverage QA

`eda_anomaly_candidates.csv` contains candidates for review and synthetic
calibration. A candidate is not automatically labelled clinically invalid.

## Code documentation and reproducibility

Key functions and decision points in `src/dynsim_tre_calibration/` include concise
docstrings and inline comments explaining **what is calculated, why the step is
needed, the grain/assumption being used, and the disclosure or reproducibility
boundary where relevant**. Comments are intentionally focused on non-obvious
logic rather than restating every Python statement, so the code remains lean and
reviewable by a third party.
