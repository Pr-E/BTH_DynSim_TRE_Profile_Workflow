"""Public entry points for the TRE EDA and calibration package.

The package intentionally exposes only the main profiling runner and validation
function so command-line scripts and third-party users have a small, stable API.
"""

from .runner import run_eda_calibration
from .validation import validate_profile

__all__ = ["run_eda_calibration", "validate_profile"]
