"""vps-3ah, vps-9he: the packages stay clean under the project's own ruff config: Pyflakes, plus no bare
except (E722), no blind except Exception that swallows (BLE001) and no print in library code (T201)."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_ruff_config_selects_the_gate_rules_and_skips_notebooks():
    text = (ROOT / "ruff.toml").read_text()
    assert 'select = ["F", "E722", "T201", "BLE001"]' in text and '"*.ipynb"' in text


def test_no_bare_except_left_in_either_package():
    hits = [f"{path.relative_to(ROOT)}:{n}" for path in sorted(ROOT.glob("villa*Sdk/*.py"))
            for n, line in enumerate(path.read_text().splitlines(), 1) if line.strip().startswith("except:")]
    assert hits == []


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
