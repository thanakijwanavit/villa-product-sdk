"""vps-v9s: tools/secret_scan.sh fails on a key anywhere in history, even one deleted later, and passes a clean repo."""
import secrets
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "secret_scan.sh"
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def repo(tmp_path):
    subprocess.run(GIT + ["init", "-q", str(tmp_path)], check=True)
    (tmp_path / "README.md").write_text("harmless\n")
    subprocess.run(GIT + ["-C", str(tmp_path), "add", "README.md"], check=True)
    subprocess.run(GIT + ["-C", str(tmp_path), "commit", "-q", "-m", "first"], check=True)
    return tmp_path


def scan(path):
    assert shutil.which("gitleaks"), "gitleaks must be on PATH (8.30.1 on G1)"
    return subprocess.run([str(SCRIPT), str(path)], capture_output=True, text=True, timeout=120)


def test_clean_repo_passes(tmp_path):
    r = scan(repo(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr


def test_key_in_deleted_history_fails(tmp_path):
    path = repo(tmp_path)
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    key = "AK" + "IA" + "".join(secrets.choice(alphabet) for _ in range(16))  # built at run time, never in this repo
    assert not key.endswith("EXAMPLE")
    (path / "config.py").write_text(f'aws_access_key_id = "{key}"\n')
    subprocess.run(GIT + ["-C", str(path), "add", "config.py"], check=True)
    subprocess.run(GIT + ["-C", str(path), "commit", "-q", "-m", "add config"], check=True)
    subprocess.run(GIT + ["-C", str(path), "rm", "-q", "config.py"], check=True)
    subprocess.run(GIT + ["-C", str(path), "commit", "-q", "-m", "remove config"], check=True)
    assert not (path / "config.py").exists()
    r = scan(path)
    assert r.returncode != 0, r.stdout + r.stderr
    assert key not in r.stdout + r.stderr  # --redact: the value is never printed
