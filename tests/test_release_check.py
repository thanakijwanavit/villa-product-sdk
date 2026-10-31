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
    # uv on PATH: `uv venv ... DIR` makes DIR/bin/python, a stub that records its calls and exits
    # with FAKE_PY_RC; `uv pip install` does nothing. No venv or package is ever really made.
    fake(b, "uv", 'if [ "$1" = venv ]; then d="${@: -1}"; mkdir -p "$d/bin"\n'
         '  printf \'#!/bin/bash\\necho "$0 $*" >> "$CALLS"\\nexit ${FAKE_PY_RC:-0}\\n\' > "$d/bin/python"\n'
         '  chmod +x "$d/bin/python"; fi')
    return r, b, tmp_path / "calls"


def run(repo, *args, **extra_env):
    r, b, calls = repo
    env = dict(os.environ, TOOLS_BIN=str(b), CALLS=str(calls), PATH=f"{b}:{os.environ['PATH']}",
               **extra_env)
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


def test_pytest_runs_in_a_venv_with_the_runtime_requirements(repo):
    p = run(repo, "--only", "pytest")
    assert p.returncode == 0, p.stdout + p.stderr
    lines = repo[2].read_text().splitlines()
    install = next(l for l in lines if " pip install " in l)
    for req in settings()["requirements"].split() + ["pytest", "setuptools", "packaging"]:
        assert req in install.split()
    assert any(l.endswith("/bin/python -m pytest -q -p no:cacheprovider tests") for l in lines)


def test_pytest_failure_stops_before_build(repo):
    p = run(repo, FAKE_PY_RC="1")
    assert "FAILED at: pytest" in p.stdout
    assert not [l for l in repo[2].read_text().splitlines() if "-m build" in l]


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


# --- scripts/release.sh uploads only what release-check passed (vps-0ax) -----------------

VERSION = settings()["version"]
DIST = [f"villaproductsdk-{VERSION}-py3-none-any.whl", f"villaproductsdk-{VERSION}.tar.gz"]


def git(r, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=r,
                          check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def rel(tmp_path):
    """A throwaway repo with release.sh, a dist/ that release-check stamped at HEAD, and a fake uvx."""
    r = tmp_path / "repo"
    (r / "scripts").mkdir(parents=True)
    shutil.copy(os.path.join(ROOT, "scripts", "release.sh"), r / "scripts" / "release.sh")
    shutil.copy(os.path.join(ROOT, "settings.ini"), r / "settings.ini")
    (r / ".gitignore").write_text("dist/\n")
    git(r, "init", "-q")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "init")
    (r / "dist").mkdir()
    for f in DIST:
        (r / "dist" / f).write_text(f)
    subprocess.run("sha256sum -- * > .release-check-ok", shell=True, cwd=r / "dist", check=True)
    (r / "dist" / ".release-check-head").write_text(git(r, "rev-parse", "HEAD") + "\n")
    b = tmp_path / "bin"
    b.mkdir()
    for t in ("uv", "uvx"):
        fake(b, t, "exit 0")
    return r, b, tmp_path / "calls"


def release(rel, *args, answer=None):
    """Run release.sh; with answer, under a pseudo-terminal (util-linux script) that types it."""
    r, b, calls = rel
    env = dict(os.environ, PATH=f"{b}:{os.environ['PATH']}", CALLS=str(calls))
    cmd = ["bash", "scripts/release.sh", *args]
    if answer is None:
        return subprocess.run(cmd, cwd=r, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=60)
    return subprocess.run(["script", "-qec", " ".join(cmd), "/dev/null"], cwd=r, env=env,
                          input=answer + "\n", capture_output=True, text=True, timeout=60)


def uploads(rel):
    calls = rel[2]
    return calls.read_text().splitlines() if calls.exists() else []


def test_upload_without_stamp_refuses(rel):
    for f in (".release-check-ok", ".release-check-head"):
        (rel[0] / "dist" / f).rename(rel[0] / "dist" / (f + ".bak"))
        p = release(rel, "--testpypi")
        assert p.returncode == 5 and "no release-check stamp" in p.stderr
        (rel[0] / "dist" / (f + ".bak")).rename(rel[0] / "dist" / f)
    assert uploads(rel) == []


def test_upload_after_new_commit_refuses(rel):
    (rel[0] / "x.txt").write_text("x")
    git(rel[0], "add", "x.txt")
    git(rel[0], "commit", "-q", "-m", "later")
    p = release(rel, "--testpypi")
    assert p.returncode == 5 and "another commit" in p.stderr
    assert uploads(rel) == []


def test_upload_of_changed_dist_file_refuses(rel):
    (rel[0] / "dist" / DIST[0]).write_text("rebuilt")
    p = release(rel, "--testpypi")
    assert p.returncode == 5 and "changed since release-check" in p.stderr
    assert uploads(rel) == []


def test_upload_of_other_version_refuses(rel):
    d = rel[0] / "dist"
    (d / "villaproductsdk-0.0.1.tar.gz").write_text("old")
    subprocess.run("sha256sum -- * > .release-check-ok", shell=True, cwd=d, check=True)
    p = release(rel, "--testpypi")
    assert p.returncode == 5 and "is not version" in p.stderr
    assert uploads(rel) == []


def test_dirty_checkout_refuses(rel):
    (rel[0] / "settings.ini").write_text((rel[0] / "settings.ini").read_text() + "\n# edit\n")
    assert release(rel, "--testpypi").returncode == 3
    assert uploads(rel) == []


def test_publish_before_testpypi_refuses(rel):
    p = release(rel, "--publish")
    assert p.returncode == 5 and "TestPyPI first" in p.stderr
    assert uploads(rel) == []


def test_valid_stamp_without_terminal_refuses(rel):
    p = release(rel, "--testpypi")
    assert p.returncode == 3 and "interactive terminal" in p.stderr
    assert uploads(rel) == []


needs_pty = pytest.mark.skipif(not shutil.which("script") or sys.platform != "linux",
                               reason="needs util-linux script for a pseudo-terminal")


@needs_pty
def test_wrong_answer_uploads_nothing(rel):
    p = release(rel, "--testpypi", answer="nope")
    assert p.returncode == 4
    assert uploads(rel) == []


@needs_pty
def test_testpypi_then_publish_upload_exactly_the_stamped_files(rel):
    stamp = (rel[0] / "dist" / ".release-check-ok").read_text().split()
    files = " ".join("dist/" + f for f in stamp[1::2])
    assert sorted(stamp[1::2]) == sorted(DIST)
    p = release(rel, "--testpypi", answer=VERSION)
    assert p.returncode == 0, p.stdout + p.stderr
    assert uploads(rel) == [f"{rel[1]}/uvx twine upload --repository testpypi {files}"]
    assert (rel[0] / "dist" / ".testpypi-ok").read_text() == \
        (rel[0] / "dist" / ".release-check-ok").read_text()
    p = release(rel, "--publish", answer=VERSION)
    assert p.returncode == 0, p.stdout + p.stderr
    assert uploads(rel)[1] == f"{rel[1]}/uvx twine upload --repository pypi {files}"
