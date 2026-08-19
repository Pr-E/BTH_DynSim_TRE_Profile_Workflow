# DynSim Generic TRE Profiler v1

This package is the TRE-side metadata profiling component for DynSim.

Its purpose is to inspect source tables inside a secure environment and create
aggregate structural/statistical metadata that can later used by DynSim outside the TRE.

## Design rule

There are **no project-specific patient counts, schemas, column names, date
ranges, category probabilities, table relationships or pathway rules embedded
in the Python profiler**.

The profiler discovers these characteristics from the source tables.

The only configuration values are generic profiling controls such as type
detection thresholds and maximum numbers of candidate columns to explore.

## What it accepts

The command-line workflow currently discovers:

- CSV
- Parquet
- Feather

The Python package works on pandas DataFrames internally, so database/query
adapters can be added without changing the profiling logic.

## What it produces

The internal aggregate profile contains:

- `tables.csv` — dimensions, missing cells, duplicates, blank rows
- `columns.csv` — schema, dtype, inferred type, missingness, uniqueness
- `identifier_candidates.csv` — automatically detected identifier-like columns
- `numeric.csv` — aggregate numeric summaries
- `categorical.csv` — aggregate category counts/proportions
- `datetime.csv` — aggregate date coverage
- `identifier_burden.csv` — rows per identifier candidate
- `within_table_links.csv` — candidate parent/child nesting behaviour
- `cross_table_links.csv` — aggregate overlap between candidate identifiers
- `temporal_intervals.csv` — aggregate intervals between detected dates
- `repeat_gaps.csv` — aggregate repeat-event gaps
- `slot_occupancy.csv` — automatically detected numbered-field occupancy
- `portable_metadata.json` — consolidated generic DynSim metadata object
- `manifest.json`

No source rows and no identifier values are written into these outputs.

## TRE workflow

From the repository root:

```bash
python scripts/run_tre_profile.py \
  --input /project/readonly \
  --output metadata_profiles/internal
```

Validate:

```bash
python scripts/validate_profile.py \
  --profile metadata_profiles/internal
```

Review the aggregate files against the exploratory analysis already performed
inside the TRE.

Only after that review, confirm the applicable disclosure-control rules
with the TRE output-checking team. The profiler does not assume a minimum
cell-count threshold or rounding rule. These values are supplied only when an
egress candidate is prepared:

```bash
python scripts/prepare_egress.py \
  --internal metadata_profiles/internal \
  --export metadata_profiles/export \
  --min-cell-count <APPROVED_THRESHOLD> \
  --round-base <APPROVED_ROUNDING_BASE> \
  --date-granularity month
```

This creates:

```text
metadata_profiles/DynSim_Aggregate_Profile_EGRESS_CANDIDATE.zip
```

The ZIP is only a candidate for disclosure review. The script does not move
anything out of the TRE and does not replace the TRE's approval process.

## What leaves the TRE after approval

The intended egress object is the disclosure-reviewed aggregate profile,
especially `portable_metadata.json` plus the supporting aggregate CSVs.

DynSim outside the TRE should use that metadata as its source of truth instead
of hard-coded project values.

## Why identifier discovery is automatic

Different projects use different identifier names. The profiler therefore
scores identifier candidates using generic signals:

- identifier-like naming
- uniqueness ratio
- missingness

It then profiles potential relationships without exporting any identifier
values.

Cross-table relationships are discovered by comparing candidate identifier
sets **inside the TRE** and writing only aggregate overlap counts and coverage.

## Important governance boundary

The `internal` profile can contain unsuppressed aggregate counts, detailed summary
statistics and exact date bounds. It should remain inside the TRE.

`prepare_egress.py` applies configurable small-cell suppression, optional count
rounding and date-bound generalisation before creating an egress candidate.

The final decision on what may leave the TRE belongs to the TRE disclosure
process.


## Disclosure-control behaviour

The export step is deliberately separate from profiling. It is not a claim that
the generated profile is automatically safe to release.

Before creating an egress candidate, obtain the applicable local TRE output
rules. The export transform can then:

- suppress positive counts below the approved threshold
- suppress derived percentages when their supporting count is unsafe
- suppress full summary rows when the contributing `n` is unsafe, so statistics
  such as mean, median, quantiles, minimum and maximum do not survive after a
  small supporting count is suppressed
- collapse small categorical cells into an `__OTHER_OR_SUPPRESSED__` group
- suppress the collapsed category if it is still below the approved threshold
- optionally round count fields
- generalise date bounds to year, month or day

The resulting ZIP remains an **egress candidate only** and must still go through
the normal TRE disclosure/output-checking process.
