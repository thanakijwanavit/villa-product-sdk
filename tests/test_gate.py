"""vps-a8a: tools/gate.sh runs pytest in a fresh venv built from requirements-dev.txt, not the host python3.
Offline: a fake `uv` makes a stub venv whose python records its calls; no package is installed."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def fake(path, body):
    path.write_text("#!/bin/bash\n" + body + "\n")
    path.chmod(0o755)


@pytest.fixture
def gate(tmp_path):
    repo = tmp_path / "repo"
    (repo / "tools").mkdir(parents=True)
    shutil.copy(ROOT / "tools" / "gate.sh", repo / "tools" / "gate.sh")
    (repo / "requirements-dev.txt").write_text("s3bz==0.1.5\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls"
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    # `uv venv ... DIR` makes DIR/bin/python, a stub that logs its args and exits FAKE_PY_RC;
    # `uv pip install` logs and exits FAKE_PIP_RC.
    fake(bin_dir / "uv",
         'echo "uv $*" >> "$CALLS"\n'
         'if [ "$1" = venv ]; then d="${@: -1}"; mkdir -p "$d/bin"\n'
         '  printf \'#!/bin/bash\\necho "python $*" >> "$CALLS"\\nexit ${FAKE_PY_RC:-0}\\n\' > "$d/bin/python"\n'
         '  chmod +x "$d/bin/python"; exit 0; fi\n'
         'exit ${FAKE_PIP_RC:-0}')

    def run(*args, **env):
        e = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", CALLS=str(calls), TMPDIR=str(tmp), **env)
        p = subprocess.run(["bash", str(repo / "tools" / "gate.sh"), *args], cwd=tmp_path, env=e,
                           capture_output=True, text=True, timeout=60)
        p.calls = calls.read_text().splitlines() if calls.exists() else []
        p.leftover = list(tmp.iterdir())
        return p
    return run, repo


def test_builds_py312_venv_from_pins_and_runs_suite(gate):
    run, repo = gate
    p = run()
    assert p.returncode == 0, p.stdout + p.stderr
    assert p.calls[0].startswith("uv venv -q -p 3.12 ")
    assert p.calls[1] == f"uv pip install -q -r {repo}/requirements-dev.txt"
    assert p.calls[2] == "python -m pytest -p no:cacheprovider -q tests"
    assert p.leftover == []  # temp venv removed


def test_pytest_args_pass_through_and_failure_propagates(gate):
    run, _ = gate
    p = run("-q", "tests/test_import.py", FAKE_PY_RC="1")
    assert p.returncode == 1
    assert p.calls[-1] == "python -m pytest -p no:cacheprovider -q tests/test_import.py"
    assert p.leftover == []


def test_venv_build_failure_is_exit_2_and_runs_no_tests(gate):
    run, _ = gate
    p = run(FAKE_PIP_RC="1")
    assert p.returncode == 2
    assert "nothing was tested" in p.stderr
    assert not [c for c in p.calls if c.startswith("python ")]
    assert p.leftover == []


def test_gate_py_overrides_version(gate):
    run, _ = gate
    p = run(GATE_PY="3.13")
    assert p.calls[0].startswith("uv venv -q -p 3.13 ")


def test_refinery_docs_and_make_name_the_gate():
    for doc in ("CLAUDE.md", "AGENTS.md"):
        text = (ROOT / doc).read_text()
        assert "## Build & Test" in text and "tools/gate.sh" in text
    assert "\ngate:\n\ttools/gate.sh\n" in (ROOT / "Makefile").read_text()
