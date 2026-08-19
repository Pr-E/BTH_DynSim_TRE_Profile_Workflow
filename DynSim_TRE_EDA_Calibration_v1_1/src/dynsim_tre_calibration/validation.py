"""Validate that a TRE EDA/calibration run produced a complete profile.

Validation checks output presence and metadata structure; it does not determine
whether an output is disclosure-approved for egress.
"""

from pathlib import Path
import json

import pandas as pd

from .profile import OUTPUTS


def validate_profile(profile_dir):
    """Check required output files and the portable metadata format after a profiling run."""
    profile_dir = Path(profile_dir)
    rows = []

    # File-presence checks catch incomplete or interrupted EDA runs before review/egress preparation.
    for filename in OUTPUTS.values():
        path = profile_dir / filename
        rows.append({
            "check": f"exists:{filename}",
            "pass": path.exists(),
            "detail": str(path),
        })

    metadata = profile_dir / "portable_metadata.json"
    rows.append({
        "check": "exists:portable_metadata.json",
        "pass": metadata.exists(),
        "detail": str(metadata),
    })

    # Structural JSON validation is intentionally separate from disclosure approval.
    if metadata.exists():
        try:
            payload = json.loads(metadata.read_text(encoding="utf-8"))
            rows.append({
                "check": "metadata_format",
                "pass": payload.get("metadata_format") == "dynsim_tre_eda_calibration_v1",
                "detail": payload.get("metadata_format"),
            })
            rows.append({
                "check": "metadata_has_tables",
                "pass": bool(payload.get("tables")),
                "detail": f"n_tables={len(payload.get('tables', {}))}",
            })
        except Exception as exc:
            rows.append({
                "check": "metadata_readable",
                "pass": False,
                "detail": repr(exc),
            })

    result = pd.DataFrame(rows)
    passed = bool(result["pass"].all()) if not result.empty else False
    return result, passed
