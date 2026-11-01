"""vps-62z: no catalog dump or other large file in the tree that goes public, and none in the sdist.

sampleData/products.csv was a 30.6 MB export of what looks like the real Villa catalog (supplier codes,
brands, content). It is no longer tracked; tests and the notebook use tests/fixtures/products_sample.csv,
synthetic rows with the export's header. Note: git history still holds the old blob; removing it needs a
history rewrite and a force-push, which only a person may do.
"""
import csv
import importlib.util
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 1_000_000
ALLOWED_LARGE: set[str] = set()  # a file over MAX_BYTES must be named here, with a reason in a comment
FIXTURE = ROOT / "tests" / "fixtures" / "products_sample.csv"


def tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    return [p for p in out.decode().split("\0") if p]


def indexed_sizes() -> dict[str, int]:
    """Size of every file as staged in the index (what a commit takes), not as it is on disk."""
    staged = subprocess.run(["git", "ls-files", "--stage", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    entries = [e.split("\t", 1) for e in staged.decode().split("\0") if e]
    objects = {meta.split()[1]: path for meta, path in entries}
    sizes = subprocess.run(["git", "cat-file", "--batch-check=%(objectname) %(objectsize)"], cwd=ROOT,
                           input="\n".join(objects).encode(), capture_output=True, check=True).stdout.decode().split("\n")
    by_object = dict(line.split() for line in sizes if line)
    return {path: int(by_object[obj]) for obj, path in objects.items()}


def test_no_tracked_file_is_over_1_mb():
    # review cx-1793496872-2554498: the staged blob counts, so a large file staged and then shrunk on disk still fails
    large = {p: n for p, n in indexed_sizes().items() if n > MAX_BYTES and p not in ALLOWED_LARGE}
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


@pytest.mark.skipif(importlib.util.find_spec("pkg_resources") is None,
                    reason="setup.py imports pkg_resources (until vps-3ug): needs setuptools<70 to build an sdist")
def test_an_sdist_built_with_local_sample_data_present_holds_none_of_it(tmp_path):
    # review cx-1793496872-2554498: build the real sdist, with a catalog export lying in sampleData/ as it would on a
    # developer's machine (ignored by git), and look inside the archive
    src = tmp_path / "src"
    for path in tracked():
        if (ROOT / path).is_file():
            (src / path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / path, src / path)
    (src / "sampleData").mkdir()
    shutil.copy2(FIXTURE, src / "sampleData" / "products.csv")
    subprocess.run([sys.executable, "setup.py", "-q", "sdist", "-d", str(tmp_path / "dist")], cwd=src,
                   check=True, capture_output=True)
    [archive] = (tmp_path / "dist").glob("*.tar.gz")
    with tarfile.open(archive) as tar:
        names = tar.getnames()
    assert names and not [n for n in names if "/sampleData/" in n], names
