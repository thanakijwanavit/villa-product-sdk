"""vps-7af: the repo's pytest.ini keeps the default run offline: live tests are deselected, unknown markers fail."""
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(tmp_path, test_body, *args):
    shutil.copy(ROOT / "pytest.ini", tmp_path / "pytest.ini")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_probe.py").write_text(textwrap.dedent(test_body))
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
                          cwd=tmp_path, capture_output=True, text=True, timeout=120)


def test_live_tests_are_deselected_by_default_and_run_on_request(tmp_path):
    body = """
        import pytest

        def test_offline():
            pass

        @pytest.mark.live
        def test_calls_aws():
            raise AssertionError("must not run by default")
    """
    r = run(tmp_path, body)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "1 passed, 1 deselected" in r.stdout
    again = tmp_path / "again"
    again.mkdir()
    r = run(again, body, "-m", "live")
    assert r.returncode == 1 and "must not run by default" in r.stdout  # selected only when asked for


def test_an_unregistered_marker_is_an_error(tmp_path):
    r = run(tmp_path, """
        import pytest

        @pytest.mark.lvie
        def test_typo():
            pass
    """)
    assert r.returncode != 0
    assert "'lvie' not found in `markers` configuration option" in r.stdout + r.stderr


def test_make_test_runs_pytest_not_the_live_notebooks():
    makefile = (ROOT / "Makefile").read_text()
    target = makefile.split("\ntest:\n", 1)[1].split("\n\n", 1)[0]
    assert "pytest" in target and "nbdev_test_nbs" not in target
