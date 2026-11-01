"""vps-3ah: the packages stay clean under the project's own ruff config (Pyflakes rules only)."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_ruff_config_selects_pyflakes_and_skips_notebooks():
    text = (ROOT / "ruff.toml").read_text()
    assert 'select = ["F"]' in text and '"*.ipynb"' in text


@pytest.mark.skipif(not (shutil.which("ruff") or shutil.which("uvx")), reason="needs ruff or uvx")
def test_pyflakes_finds_nothing_in_either_package():
    cmd = ["ruff"] if shutil.which("ruff") else ["uvx", "ruff"]
    run = subprocess.run([*cmd, "check", "--no-cache", "villaProductSdk", "villaInventorySdk"], cwd=ROOT,
                         capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stdout + run.stderr


@pytest.mark.skipif(not (shutil.which("ruff") or shutil.which("uvx")), reason="needs ruff or uvx")
def test_pyflakes_finds_nothing_in_the_whole_repo():
    # vps-n8y: the refinery gate runs `ruff check .`, which also covers tests/, tools/ and scripts/.
    cmd = ["ruff"] if shutil.which("ruff") else ["uvx", "ruff"]
    run = subprocess.run([*cmd, "check", "--no-cache", "."], cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stdout + run.stderr
