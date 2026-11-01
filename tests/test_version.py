"""vps-3ug: the package has one version, in settings.ini (setup.py's source) and villaProductSdk/__init__.py."""
import sys
from configparser import ConfigParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # the checkout's package, whichever directory pytest runs from

import villaProductSdk  # noqa: E402  (its __init__ holds only __version__)


def test_version_matches_settings():
    config = ConfigParser(delimiters=["="])
    config.read(ROOT / "settings.ini")
    assert config["DEFAULT"]["version"] == villaProductSdk.__version__
