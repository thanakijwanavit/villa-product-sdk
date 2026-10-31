"""Offline tests for the release gate (bead vps-0ax): tools/release_check.sh,
tools/check_wheel.py and the packaging settings. Run: pytest -q tests
"""
import configparser
import os
import shutil
import subprocess
import sys
import zipfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_wheel  # noqa: E402

GATES = ["clean-tree", "clean-nbs", "diff-nbs", "pytest", "build", "contents", "twine",
         "install", "audit", "secrets"]


def settings():
    c = configparser.ConfigParser(delimiters=["="])
    c.read(os.path.join(ROOT, "settings.ini"))
    return c["DEFAULT"]


# --- packaging settings -------------------------------------------------------------

def test_packages_are_the_intended_ones():
    pkgs = settings()["packages"].split()
    assert pkgs[0] == "villaProductSdk"
    assert set(pkgs) <= {"villaProductSdk", "villaInventorySdk"}
    for p in pkgs:
        assert os.path.isfile(os.path.join(ROOT, p, "__init__.py"))


def test_leftovers_not_tracked():
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                             check=True).stdout.split()
    assert not [f for f in tracked if f.startswith(("nbdev_template/", "dask-worker-space/"))]
    assert ".github/workflows/main.yml" not in tracked


def test_min_python_is_lowest_tested():
    s = settings()
    tested = s["tested_pythons"].split()
    assert "3.12" in tested
    assert s["min_python"] == min(tested, key=lambda v: tuple(map(int, v.split("."))))


def test_setup_classifiers_match_tested_pythons():
    out = subprocess.run([sys.executable, "setup.py", "--classifiers"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.splitlines()
    versions = sorted(c.rsplit(" :: ", 1)[1] for c in out
                      if c.startswith("Programming Language :: Python :: 3."))
    assert versions == sorted(settings()["tested_pythons"].split())


# --- check_wheel.py -----------------------------------------------------------------

def test_wheel_with_only_listed_packages_passes():
    names = ["villaProductSdk/__init__.py", "villaProductSdk/products.py",
             "villaInventorySdk/__init__.py", "villaProductSdk-0.0.19.dist-info/METADATA"]
    assert check_wheel.problems(names, ["villaProductSdk", "villaInventorySdk"]) == []


def test_wheel_with_leftover_package_fails():
    names = ["villaProductSdk/__init__.py", "nbdev_template/__init__.py", "x.py"]
    found = check_wheel.problems(names, ["villaProductSdk"])
    assert found == ["not a listed package: nbdev_template/__init__.py",
                     "not a listed package: x.py"]


def test_wheel_missing_listed_package_fails(tmp_path):
    whl = tmp_path / "a-1-py3-none-any.whl"
    with zipfile.ZipFile(whl, "w") as zf:
        zf.writestr("villaProductSdk/__init__.py", "")
        zf.writestr("a-1.dist-info/METADATA", "")
    assert check_wheel.main([str(whl), "villaProductSdk"]) == 0
    assert check_wheel.main([str(whl), "villaProductSdk", "villaInventorySdk"]) == 1


# --- release_check.sh against fake tools --------------------------------------------

def fake(bin_dir, name, body):
    p = bin_dir / name
    p.write_text("#!/bin/bash\necho \"$0 $*\" >> \"$CALLS\"\n" + body + "\n")
    p.chmod(0o755)


@pytest.fixture
def repo(tmp_path):
    """A throwaway git repo holding the gate script, settings.ini and fake tools."""
    r = tmp_path / "repo"
    (r / "tools").mkdir(parents=True)
    for f in ("release_check.sh", "check_wheel.py", "import_all.py"):
        shutil.copy(os.path.join(ROOT, "tools", f), r / "tools" / f)
    shutil.copy(os.path.join(ROOT, "settings.ini"), r / "settings.ini")
    (r / "a.ipynb").write_text("{}\n")
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init"]):
        subprocess.run(["git", *args], cwd=r, check=True)
    b = tmp_path / "bin"
    b.mkdir()
    for t in ("nbdev_clean_nbs", "nbdev_diff_nbs", "pytest", "python", "twine", "pip-audit",
              "gitleaks"):
        fake(b, t, "exit 0")
    return r, b, tmp_path / "calls"


def run(repo, *args):
    r, b, calls = repo
    env = dict(os.environ, TOOLS_BIN=str(b), CALLS=str(calls))
    return subprocess.run(["bash", str(r / "tools" / "release_check.sh"), *args], cwd=r, env=env,
                          capture_output=True, text=True, timeout=60)


def called(repo):
    calls = repo[2]
    return [os.path.basename(l.split()[0]) for l in calls.read_text().splitlines()] \
        if calls.exists() else []


def test_list_names_the_gates_in_order(repo):
    p = run(repo, "--list")
    assert p.returncode == 0
    assert p.stdout.split() == GATES


def test_unknown_gate_is_a_usage_error(repo):
    assert run(repo, "--only", "nope").returncode == 2
    assert run(repo, "--bogus").returncode == 2


def test_stops_at_first_failure(repo):
    fake(repo[1], "nbdev_diff_nbs", "echo 'diff -ru a b'")
    p = run(repo)
    assert p.returncode == 1
    assert "release-check FAILED at: diff-nbs" in p.stdout
    assert called(repo) == ["nbdev_clean_nbs", "nbdev_diff_nbs"]  # pytest and later never ran


def test_failing_tool_fails_gate_even_when_tree_stays_clean(repo):
    # nbdev_clean_nbs fails without touching any notebook: set -e must still stop the gate.
    fake(repo[1], "nbdev_clean_nbs", "exit 3")
    p = run(repo)
    assert p.returncode == 1
    assert "release-check FAILED at: clean-nbs (exit 3)" in p.stdout
    assert called(repo) == ["nbdev_clean_nbs"]


def test_notebook_changed_by_clean_fails(repo):
    fake(repo[1], "nbdev_clean_nbs", "echo '{\"x\": 1}' > a.ipynb")
    p = run(repo)
    assert p.returncode == 1
    assert "nbdev_clean_nbs changed notebooks" in p.stdout
    assert "FAILED at: clean-nbs" in p.stdout


def test_dirty_tree_fails_first(repo):
    (repo[0] / "a.ipynb").write_text('{"edited": 1}\n')
    p = run(repo)
    assert p.returncode == 1
    assert "FAILED at: clean-tree" in p.stdout
    assert called(repo) == []


def test_pytest_failure_stops_before_build(repo):
    fake(repo[1], "pytest", "exit 1")
    p = run(repo)
    assert "FAILED at: pytest" in p.stdout
    assert "python" not in called(repo)


def test_secret_finding_fails(repo):
    fake(repo[1], "gitleaks", "exit 1")
    p = run(repo, "--only", "secrets")
    assert p.returncode == 1
    assert "FAILED at: secrets" in p.stdout
    assert called(repo) == ["gitleaks"]


def test_missing_settings_is_an_error(repo):
    (repo[0] / "settings.ini").write_text("[DEFAULT]\npackages = villaProductSdk\n")
    p = run(repo)
    assert p.returncode != 0
    assert "needs non-empty packages and tested_pythons" in p.stderr
    assert called(repo) == []
