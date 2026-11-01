"""vps-9kk, vps-2e0: settings.ini keeps urllib3 off releases with fixed advisories without capping botocore or requests.

setup.py builds install_requires by splitting settings.ini's `requirements` on whitespace, so these tests
read it the same way; Requirement() raises InvalidRequirement if a space cut one requirement in two.
"""
from configparser import ConfigParser
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parent.parent


def urllib3_specifier():
    config = ConfigParser(delimiters=["="])
    config.read(ROOT / "settings.ini")
    requirements = [Requirement(token) for token in config["DEFAULT"].get("requirements", "").split()]
    found = [req for req in requirements if req.name.lower() == "urllib3"]
    assert len(found) == 1, found
    return found[0].specifier


def test_urllib3_has_a_floor_and_no_pin_or_cap():
    # == froze installs on 1.25.10; <, <= or ~= would cap what botocore and requests can resolve.
    operators = {spec.operator for spec in urllib3_specifier()}
    assert operators and operators <= {">=", ">", "!="}, operators


def test_urllib3_floor_skips_releases_with_fixes_on_the_1_26_line():
    specifier = urllib3_specifier()
    # 1.25.10 is the old pin; 1.26.18 is the last release before the CVE-2024-37891 fix in 1.26.19.
    for version in ("1.25.10", "1.26.5", "1.26.17", "1.26.18"):
        assert not specifier.contains(version), version
    # botocore requires urllib3<1.27 on Python < 3.10; 2.8.0 is the newest release, used on 3.10+.
    for version in ("1.26.19", "1.26.20", "2.8.0"):
        assert specifier.contains(version), version
