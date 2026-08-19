# TRE runbook

## 1. Ingress

Ingress this repository/code package through the approved TRE code-ingress route.

No source data are packaged with the code.

## 2. Confirm environment

```bash
python --version
python -c "import pandas, numpy; print('pandas', pandas.__version__, 'numpy', numpy.__version__)"
```

No editable install is required. The scripts add the local `src` directory to
the Python path.

## 3. Profile the available TRE tables

```bash
python scripts/run_tre_profile.py --input /project/readonly --output metadata_profiles/internal
```

The profiler scans supported table files automatically. There is no six-table
name list in the code.

## 4. Validate

```bash
python scripts/validate_profile.py --profile metadata_profiles/internal
```

## 5. Analytical verification inside TRE

Compare the generated aggregate files with the existing EDA results. Key files:

```text
tables.csv
columns.csv
identifier_candidates.csv
identifier_burden.csv
within_table_links.csv
cross_table_links.csv
numeric.csv
categorical.csv
datetime.csv
temporal_intervals.csv
repeat_gaps.csv
slot_occupancy.csv
```

This is where project-specific interpretation occurs. The profiler itself does
not assume which candidate is the patient ID, spell ID, event ID or referral ID.

## 6. Disclosure preparation

Obtain the applicable disclosure-control rules from the TRE team.

Then create an export candidate using the threshold, rounding and date
generalisation rules confirmed by the TRE output-checking team:

```bash
python scripts/prepare_egress.py \
  --internal metadata_profiles/internal \
  --export metadata_profiles/export \
  --min-cell-count <APPROVED_THRESHOLD> \
  --round-base <APPROVED_ROUNDING_BASE> \
  --date-granularity month
```

The export transform suppresses unsafe supporting counts **and the derived
statistics that depend on them**. This avoids leaving means, medians, quantiles,
minimums, maximums or percentages visible after a small contributing count has
been suppressed.

## 7. Submit for approved egress

Submit:

```text
metadata_profiles/DynSim_Aggregate_Profile_EGRESS_CANDIDATE.zip
```

through the normal TRE disclosure process.

## 8. Outside the TRE

After approval, place the aggregate ZIP with the external DynSim development
environment. The key machine-readable input is:

```text
portable_metadata.json
```

The next DynSim generator layer should consume this standard metadata object
and build its synthetic tables from the discovered structures rather than from
project-specific constants.
