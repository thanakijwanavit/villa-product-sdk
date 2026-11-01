"""vps-b5i: tools/check_licenses.py on pure functions, no network and no installed packages needed."""
import importlib.util
from email.message import Message
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_licenses", ROOT / "tools" / "check_licenses.py")
cl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cl)


def meta(**fields):
    m = Message()
    for key, value in fields.items():
        for v in value if isinstance(value, list) else [value]:
            m[key.replace("_", "-")] = v
    return m


def test_classify_permissive_ok():
    for lic in ("MIT", "Apache-2.0", "BSD-3-Clause", "MPL-2.0", "PSF-2.0", "Apache-2.0 OR BSD-2-Clause"):
        assert cl.classify("pkg", lic, {})[0], lic
    assert cl.license_of(meta(License_Expression="MIT")) == "MIT"
    # a vague License value falls back to the classifiers (python-dateutil says "Dual License")
    assert cl.license_of(meta(License="Dual License", Classifier=["License :: OSI Approved :: BSD License"])) == "BSD License"


def test_classify_gpl_blocked():
    for lic in ("GPL-3.0-only", "AGPL-3.0", "LGPL-2.1-or-later", "SSPL-1.0", "GNU General Public License v2 (GPLv2)"):
        ok, why = cl.classify("pkg", lic, {"pkg": "even allowlisted"})
        assert not ok and "copyleft" in why, lic


def test_unknown_needs_allowlist(tmp_path):
    assert not cl.classify("odd-pkg", "", {})[0]
    assert not cl.classify("odd-pkg", "UNKNOWN", {})[0]
    allow = tmp_path / "allow.txt"
    allow.write_text("# comment\nOdd_Pkg: license is in the repo's LICENSE file, MIT\n")
    ok, why = cl.classify("odd-pkg", "", cl.load_allowlist(allow))
    assert ok and "MIT" in why


def test_closure_ignores_unrelated_distributions():
    installed = {  # name -> Requires-Dist; python-apt is installed (GPL) but nothing we use needs it
        "sdk-dep": ["requests (>=2)", 'pysocks ; extra == "socks"', 'tomli ; python_version < "3.0"'],
        "requests": ["urllib3<3,>=1.21.1", "certifi>=2017.4.17"],
        "urllib3": [],
        "certifi": [],
        "python-apt": [],
        "pysocks": [],
        "tomli": [],
    }
    found = cl.closure(["sdk-dep"], lambda n: installed.get(cl.normalize(n)))
    assert [cl.normalize(n) for n in found] == ["certifi", "requests", "sdk-dep", "urllib3"]
    assert cl.requirement_names("dataclasses-json urllib3==1.25.10 awsSchema") == ["dataclasses-json", "urllib3", "awsSchema"]
