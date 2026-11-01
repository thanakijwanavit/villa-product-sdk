"""vps-eht: tools/scan_pypi_artifacts.py reports a key hidden in a published archive, never prints it, and refuses
archives that would write outside their own directory. Runs offline with --local."""
import io
import secrets
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "scan_pypi_artifacts.py"


def fake_key():
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    key = "AK" + "IA" + "".join(secrets.choice(alphabet) for _ in range(16))  # built at run time, never in this repo
    assert not key.endswith("EXAMPLE")
    return key


def add(tar, name, text):
    data = text.encode()
    info = tarfile.TarInfo(name)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


def scan(*args):
    assert shutil.which("gitleaks"), "gitleaks must be on PATH (8.30.1 on G1)"
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, timeout=120)


def test_clean_archives_pass(tmp_path):
    with tarfile.open(tmp_path / "pkg-0.1.tar.gz", "w:gz") as t:
        add(t, "pkg-0.1/pkg/__init__.py", "x = 1\n")
    with zipfile.ZipFile(tmp_path / "pkg-0.1-py3-none-any.whl", "w") as z:
        z.writestr("pkg/__init__.py", "x = 1\n")
    r = scan("--local", tmp_path, "--work", tmp_path / "w")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "2 files scanned, 0 findings, 0 errors" in r.stdout


def test_key_in_sdist_only_file_fails_and_is_redacted(tmp_path):
    key = fake_key()
    with tarfile.open(tmp_path / "pkg-0.2.tar.gz", "w:gz") as t:
        add(t, "pkg-0.2/pkg/__init__.py", "x = 1\n")
        add(t, "pkg-0.2/.env", f'AWS_ACCESS_KEY_ID="{key}"\n')  # the uncommitted file case
    md = tmp_path / "report.md"
    r = scan("--local", tmp_path, "--work", tmp_path / "w", "--markdown", md)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "pkg-0.2/.env" in r.stdout
    assert key not in r.stdout + r.stderr + md.read_text()


def test_key_in_wheel_fails(tmp_path):
    key = fake_key()
    with zipfile.ZipFile(tmp_path / "pkg-0.3-py3-none-any.whl", "w") as z:
        z.writestr("pkg/config.py", f'aws_access_key_id = "{key}"\n')
    r = scan("--local", tmp_path, "--work", tmp_path / "w")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "pkg/config.py" in r.stdout and key not in r.stdout + r.stderr


def test_path_traversal_archive_is_refused(tmp_path):
    with zipfile.ZipFile(tmp_path / "evil-0.1-py3-none-any.whl", "w") as z:
        z.writestr("../../escaped.py", "x = 1\n")
    r = scan("--local", tmp_path, "--work", tmp_path / "w")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "unsafe path" in r.stderr
    assert not (tmp_path / "escaped.py").exists() and not (tmp_path.parent / "escaped.py").exists()
