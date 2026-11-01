"""vps-53u: importing the SDK leaves the application's root logger alone (no handler added, level unchanged)."""
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROBE = textwrap.dedent(
    """
    import json, logging, sys, types
    # s3bz needs network-era deps; the modules only need its names at import time
    s3bz = types.ModuleType("s3bz"); inner = types.ModuleType("s3bz.s3bz")
    inner.S3 = type("S3", (), {}); inner.Requests = type("Requests", (), {})
    s3bz.s3bz = inner; sys.modules["s3bz"] = s3bz; sys.modules["s3bz.s3bz"] = inner
    import villaProductSdk.products, villaProductSdk.inventory, villaInventorySdk.inventory
    root = logging.getLogger()
    print(json.dumps({"handlers": [type(h).__name__ for h in root.handlers], "level": root.level,
                      "sdk": [type(h).__name__ for h in logging.getLogger("villaProductSdk").handlers]}))
    """
)


def test_import_leaves_root_logger_untouched():
    r = subprocess.run([sys.executable, "-c", PROBE], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    import json

    seen = json.loads(r.stdout.strip().splitlines()[-1])
    assert seen["handlers"] == []
    assert seen["level"] == 30  # logging.WARNING, Python's default
    assert seen["sdk"] == ["NullHandler"]
