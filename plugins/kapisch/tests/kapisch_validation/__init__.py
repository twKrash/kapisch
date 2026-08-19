"""Validator tests discoverable from either supported unittest start path."""

from pathlib import Path

# With ``unittest discover -s tests``, this package has the same import name as
# the source package. Include the source directory so imports such as
# ``kapisch_validation.cli`` continue to resolve during that discovery mode.
__path__.append(str(Path(__file__).resolve().parents[2] / "kapisch_validation"))
