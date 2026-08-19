# Architecture

```text
SOURCE TABLES INSIDE TRE
        |
        v
Generic discovery
        |
        +--> schema / missingness / uniqueness
        +--> identifier candidates
        +--> numeric distributions
        +--> categorical distributions
        +--> datetime ranges
        +--> repeated-record burden
        +--> within-table nesting candidates
        +--> cross-table identifier overlap
        +--> temporal intervals
        +--> repeat gaps
        +--> numbered-slot occupancy
        |
        v
INTERNAL AGGREGATE PROFILE
        |
        | TRE-side analytical review
        v
Disclosure-control transform
        |
        v
EXPORT AGGREGATE PROFILE
        |
        | approved TRE egress only
        v
portable_metadata.json
        |
        v
DYNSIM OUTSIDE TRE
        |
        v
LOW-FIDELITY SYNTHETIC TABLES
```

## Hard-coded versus generic

The profiler may hard-code generic algorithms, for example:

- how uniqueness ratios are calculated
- how quantiles are calculated
- how a date-like column is detected
- how candidate IDs are scored
- how overlap/Jaccard measures are calculated

It does **not** hard-code project facts, for example:

- table names
- patient counts
- column lists
- identifier names
- category probabilities
- date ranges
- overlap counts
- event counts
- pathway definitions
- cohort labels
- BTH/Sports Centre logic

Those facts come from the data being profiled.
