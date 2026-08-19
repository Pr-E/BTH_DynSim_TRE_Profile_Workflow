# TRE runbook

## 1. Ingress code only

No data or aggregate findings should be committed to the repository.

## 2. Run the EDA + calibration

```bash
python scripts/run_tre_eda_calibration.py \
  --input /project/readonly \
  --output metadata_profiles/internal
```

## 3. Validate

```bash
python scripts/validate_profile.py \
  --profile metadata_profiles/internal
```

## 4. Reconcile with the earlier six-table EDA

Check at minimum:

- table dimensions / blank rows / exact duplicates
- resolved patient and event keys
- referral/attendance/spell/episode burden
- inpatient spell nesting
- temporal chronology anomalies
- LOS distributions
- repeated-event gaps
- slot occupancy
- patient demographics/categories
- cross-table patient coverage/overlap

Only investigate discrepancies. Do not manually overwrite the profile with
expected values.

## 5. Review the richer calibration

Check:

- numeric distributions
- categorical distributions
- seasonality
- missingness dependencies
- numeric correlations
- categorical associations/joint distributions

## 6. Prepare disclosure-controlled output only after approval rules are known

```bash
python scripts/prepare_egress.py \
  --internal metadata_profiles/internal \
  --export metadata_profiles/export \
  --min-cell-count <APPROVED_THRESHOLD> \
  --round-base <APPROVED_ROUNDING_BASE>
```

## 7. External workflow

Use the approved aggregate metadata to calibrate DynSim, generate synthetic
tables, develop the full analytical workflow outside the TRE, then run the
validated workflow against the main TRE data.
