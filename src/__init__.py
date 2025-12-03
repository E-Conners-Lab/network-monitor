"""Network Monitor - Enterprise network monitoring with automated remediation."""

from pathlib import Path


def _get_version() -> str:
    """Read version from VERSION file."""
    version_file = Path(__file__).parent.parent / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return "0.0.0-dev"


__version__ = _get_version()
