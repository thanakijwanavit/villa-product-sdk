"""vps-62z: no catalog dump or other large file in the tree that goes public, and none in the sdist.

sampleData/products.csv was a 30.6 MB export of what looks like the real Villa catalog (supplier codes,
brands, content). It is no longer tracked; tests and the notebook use tests/fixtures/products_sample.csv,
synthetic rows with the export's header. Note: git history still holds the old blob; removing it needs a
history rewrite and a force-push, which only a person may do.
"""
import csv
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 1_000_000
ALLOWED_LARGE: set[str] = set()  # a file over MAX_BYTES must be named here, with a reason in a comment
FIXTURE = ROOT / "tests" / "fixtures" / "products_sample.csv"


def tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    return [p for p in out.decode().split("\0") if p]


def test_no_tracked_file_is_over_1_mb():
    large = {p: (ROOT / p).stat().st_size for p in tracked()
             if (ROOT / p).is_file() and (ROOT / p).stat().st_size > MAX_BYTES and p not in ALLOWED_LARGE}
    assert large == {}, large


def test_the_catalog_export_is_not_tracked_and_stays_ignored():
    assert "sampleData/products.csv" not in tracked()
    ignored = subprocess.run(["git", "check-ignore", "-q", "sampleData/products.csv"], cwd=ROOT)
    assert ignored.returncode == 0, "sampleData/*.csv must stay in .gitignore"


def test_the_sample_fixture_is_small_and_synthetic():
    with FIXTURE.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert 1 <= len(rows) <= 20
    assert {"cprcode", "iprcode", "pr_sucode1", "pr_engname"} <= set(rows[0])
    assert all(r["pr_engname"].startswith("SAMPLE ITEM") and r["pr_sucode1"].startswith("SU") for r in rows)


def test_the_sdist_cannot_pick_up_sample_data():
    # setup.py lists packages with find_packages() and MANIFEST.in adds files; neither may name sampleData
    manifest = (ROOT / "MANIFEST.in").read_text()
    assert not re.search(r"(?im)^\s*(graft\s+(\.|sampleData)|(recursive-)?include\s+sampleData)", manifest), manifest
    assert "sampleData" not in (ROOT / "setup.py").read_text()
