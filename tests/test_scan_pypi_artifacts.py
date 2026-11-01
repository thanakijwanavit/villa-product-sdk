"""vps-eht: tools/scan_pypi_artifacts.py reports a key hidden in a published archive, never prints it, cannot be told
by the package itself to look away, and fails closed. Runs offline: --local archives, or PyPI answers faked in-process.
Fake keys are built at run time and never stored in this repo."""
import hashlib
import importlib.util
import io
import json
import secrets
import shutil
import subprocess
import sys
import tarfile
import urllib.error
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "scan_pypi_artifacts.py"


def fake_key():
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    key = "AK" + "IA" + "".join(secrets.choice(alphabet) for _ in range(16))
    assert not key.endswith("EXAMPLE")
    return key


def add(tar, name, data):
    data = data.encode() if isinstance(data, str) else data
    info = tarfile.TarInfo(name)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


def wheel(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buf.getvalue()


def scan(*args):
    assert shutil.which("gitleaks"), "gitleaks must be on PATH (8.30.1 on G1)"
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, timeout=120)


def load_scanner():
    spec = importlib.util.spec_from_file_location("scan_pypi_artifacts", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fake_pypi(monkeypatch, mod, files, listed_sha=None, listing_down=False):
    """Answer the PyPI JSON API and file downloads for package 'pkg' from memory."""
    def urlopen(url, timeout=None):
        if url.startswith("https://pypi.org/pypi/"):
            if listing_down:
                raise urllib.error.URLError("offline")
            release = [{"filename": name, "url": "https://files.pythonhosted.org/packages/xx/" + name,
                        "digests": {"sha256": listed_sha or hashlib.sha256(data).hexdigest()}}
                       for name, data in files.items()]
            return io.BytesIO(json.dumps({"releases": {"0.1": release}}).encode())
        return io.BytesIO(files[url.rsplit("/", 1)[1]])
    monkeypatch.setattr(mod.urllib.request, "urlopen", urlopen)


def test_clean_archives_pass(tmp_path):
    with tarfile.open(tmp_path / "pkg-0.1.tar.gz", "w:gz") as t:
        add(t, "pkg-0.1/pkg/__init__.py", "x = 1\n")
    (tmp_path / "pkg-0.1-py3-none-any.whl").write_bytes(wheel({"pkg/__init__.py": "x = 1\n"}))
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
    assert "pkg-0.2/.env:1 [aws-access-token]" in r.stdout
    assert "`pkg-0.2/.env:1` [aws-access-token]" in md.read_text()
    assert key not in r.stdout + r.stderr + md.read_text()


def test_key_in_wheel_fails(tmp_path):
    key = fake_key()
    (tmp_path / "pkg-0.3-py3-none-any.whl").write_bytes(wheel({"pkg/config.py": f'aws_access_key_id = "{key}"\n'}))
    r = scan("--local", tmp_path, "--work", tmp_path / "w")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "pkg/config.py:1" in r.stdout and key not in r.stdout + r.stderr


def test_package_cannot_allowlist_its_own_keys(tmp_path):
    """A shipped .gitleaks.toml, .gitleaksignore or gitleaks:allow comment must not hide anything."""
    k1, k2 = fake_key(), fake_key()
    content = (tmp_path / "w").resolve() / "x" / "0000" / "content"  # where the scanner unpacks the only archive
    ignore = "".join(f"{content / 'pkg' / f}:aws-access-token:1\n" for f in ("a.py", "b.py"))
    (tmp_path / "pkg-0.4-py3-none-any.whl").write_bytes(wheel({
        ".gitleaks.toml": "[extend]\nuseDefault = true\n[[allowlists]]\npaths = ['''.*''']\n",
        ".gitleaksignore": ignore,
        "pkg/a.py": f'aws_access_key_id = "{k1}"  # gitleaks:allow\n',
        "pkg/b.py": f'aws_access_key_id = "{k2}"\n',
    }))
    r = scan("--local", tmp_path, "--work", tmp_path / "w")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "pkg/a.py:1" in r.stdout and "pkg/b.py:1" in r.stdout


def test_archive_inside_a_package_is_scanned(tmp_path):
    key = fake_key()
    with tarfile.open(tmp_path / "pkg-0.5.tar.gz", "w:gz") as t:
        add(t, "pkg-0.5/tests/fixtures.zip", wheel({"conf/settings.py": f'aws_access_key_id = "{key}"\n'}))
    r = scan("--local", tmp_path, "--work", tmp_path / "w")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "pkg-0.5/tests/fixtures.zip!conf/settings.py" in r.stdout and key not in r.stdout + r.stderr


def test_path_traversal_archive_is_refused(tmp_path):
    (tmp_path / "evil-0.1-py3-none-any.whl").write_bytes(wheel({"../../escaped.py": "x = 1\n"}))
    r = scan("--local", tmp_path, "--work", tmp_path / "w")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "unsafe path" in r.stderr
    assert not (tmp_path / "escaped.py").exists() and not (tmp_path.parent / "escaped.py").exists()


def test_nothing_to_scan_is_an_error(tmp_path):
    (tmp_path / "dist").mkdir()
    r = scan("--local", tmp_path / "dist", "--work", tmp_path / "w")
    assert r.returncode == 2 and "nothing to scan" in r.stderr


def test_pypi_mode_finds_key_in_wheel_metadata(monkeypatch, tmp_path, capsys):
    """gitleaks' default allowlist skips *.dist-info/, where a wheel keeps its README (METADATA)."""
    key = fake_key()
    mod = load_scanner()
    whl = wheel({"pkg/__init__.py": "x = 1\n", "pkg-0.1.dist-info/METADATA": f"Description: key = {key}\n"})
    fake_pypi(monkeypatch, mod, {"pkg-0.1-py3-none-any.whl": whl})
    md = tmp_path / "report.md"
    assert mod.main(["pkg", "--work", str(tmp_path / "w"), "--markdown", str(md)]) == 1
    out = capsys.readouterr()
    assert "FINDING pkg 0.1 pkg-0.1-py3-none-any.whl :: pkg-0.1.dist-info/METADATA:1 [aws-access-token]" in out.out
    report = md.read_text()
    assert f"| pkg | 0.1 | pkg-0.1-py3-none-any.whl | {hashlib.sha256(whl).hexdigest()[:12]} | 2 | ok |" in report
    assert "| pkg | 1 | 1 | 1 | 0 |" in report and "Not triaged yet" in report
    assert key not in out.out + out.err + report


def test_pypi_mode_fails_closed(monkeypatch, tmp_path, capsys):
    mod = load_scanner()
    fake_pypi(monkeypatch, mod, {"pkg-0.1-py3-none-any.whl": wheel({"pkg/__init__.py": "x = 1\n"})},
              listed_sha="0" * 64)
    assert mod.main(["pkg", "--work", str(tmp_path / "w1")]) == 2
    assert "sha256 mismatch" in capsys.readouterr().err
    assert not [p for p in (tmp_path / "w1" / "dl").rglob("*") if p.is_file()]  # a bad download is not kept
    fake_pypi(monkeypatch, mod, {}, listing_down=True)
    assert mod.main(["pkg", "--work", str(tmp_path / "w2")]) == 2
    assert "cannot list its PyPI files" in capsys.readouterr().err
