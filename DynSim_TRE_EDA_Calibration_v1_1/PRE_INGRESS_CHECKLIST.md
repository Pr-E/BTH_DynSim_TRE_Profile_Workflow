# Pre-ingress checklist

- code/config/docs only
- no TRE-derived counts or distributions committed
- no patient-level records or hashes committed
- no synthetic/output files committed
- source tables discovered at runtime
- no disclosure threshold hard-coded
- aggregate profile written only after EDA runs inside the TRE
- internal outputs remain inside the TRE
- approved aggregate outputs only are used outside the TRE
