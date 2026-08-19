# Pre-ingress checklist

This package is designed for code ingress only. It contains no source patient data.

Before sending the repository for TRE ingress, confirm:

- the repository contains only code, generic configuration and documentation
- no patient-level extracts, hashes, outputs or screenshots are committed
- `metadata_profiles/`, generated ZIPs, temporary files and caches are excluded from version control
- the TRE source path is supplied at runtime
- disclosure thresholds and rounding rules are not hard-coded
- the egress step is run only after the TRE output-checking team confirms the applicable rules

Inside the TRE:

```bash
python scripts/run_tre_profile.py \
  --input /project/readonly \
  --output metadata_profiles/internal

python scripts/validate_profile.py \
  --profile metadata_profiles/internal
```

Do not prepare an egress candidate until the internal aggregate profile has been
reviewed and the applicable disclosure-control rules have been confirmed.

The profiler writes aggregate metadata only. It does not write source rows or
identifier values to its outputs.
