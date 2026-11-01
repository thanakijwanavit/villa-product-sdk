"""Regression coverage for Python 3.12 dependency imports (vps-b7v)."""

import os
from pathlib import Path
import subprocess
import sys


def test_products_module_imports():
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(repo_root), env.get("PYTHONPATH")))
    )
    env["AWS_EC2_METADATA_DISABLED"] = "true"
    code = (
        "import villaProductSdk.products, villaProductSdk.schema\n"
        "assert hasattr(villaProductSdk.products, 'ProductSdk')\n"
        "assert hasattr(villaProductSdk.products, 'FunctionNames')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
