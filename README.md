## BTH Dynamic Simulator (DynSim) TRE Profile Workflow

This repository contains the **TRE-side EDA and calibration workflow** used to profile the BTH source datasets before downstream synthetic data generation.

It reproduces the core **structural, statistical, temporal, missingness, anomaly and cross-table relationship checks** performed during the initial TRE exploration, then converts those findings into structured aggregate metadata for DynSim calibration.

No patient-level records or identifiers are exported, and no BTH-specific statistical findings are hard-coded into the workflow; these are derived only when the code runs against the source data inside the TRE.

Any resulting aggregate metadata must be reviewed and pass the approved **TRE disclosure-control process** before being used outside the TRE to generate low-fidelity synthetic data and support development of the wider analytical workflow.
