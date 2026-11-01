"""vps-eht: tools/scan_pypi_artifacts.py reports a key hidden in a published archive, never prints it, cannot be told
by the package or the caller's environment to look away, and never counts a file it did not read as clean. Offline:
--local archives, or PyPI answers faked in-process. Fake keys are built at run time and never stored in this repo."""
import hashlib
import importlib.util
import io
import json
import os
import py_compile
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


def add(tar, name, data=b"", kind=tarfile.REGTYPE, link=""):
    data = data.encode() if isinstance(data, str) else data
    info = tarfile.TarInfo(name)
    info.type, info.linkname, info.size = kind, link, len(data) if kind == tarfile.REGTYPE else 0
    tar.addfile(info, io.BytesIO(data) if kind == tarfile.REGTYPE else None)


def wheel(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buf.getvalue()


def scan(*args, env=None):
    assert shutil.which("gitleaks"), "gitleaks must be on PATH (8.30.1 on G1)"
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, timeout=120,
                          env=env)


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
        add(t, "pkg-0.1/pkg/empty.py")  # empty files hold nothing to read
    (tmp_path / "pkg-0.1-py3-none-any.whl").write_bytes(wheel({"pkg/__init__.py": "x = 1\n"}))
    r = scan("--local", tmp_path, "--work", tmp_path / "w")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "2 files checked, 0 findings, 0 errors" in r.stdout


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
    """A shipped .gitleaks.toml or a gitleaks:allow comment must not hide anything."""
    k1, k2 = fake_key(), fake_key()
    (tmp_path / "pkg-0.4-py3-none-any.whl").write_bytes(wheel({
        ".gitleaks.toml": "[extend]\nuseDefault = true\n[[allowlists]]\npaths = ['''.*''']\n",
        "pkg/a.py": f'aws_access_key_id = "{k1}"  # gitleaks:allow\n',
        "pkg/b.py": f'aws_access_key_id = "{k2}"\n',
    }))
    r = scan("--local", tmp_path, "--work", tmp_path / "w")
    assert "pkg/a.py:1" in r.stdout and "pkg/b.py:1" in r.stdout, r.stdout + r.stderr
    assert r.returncode == 2 and ": .gitleaks.toml" in r.stderr  # gitleaks never reads files named gitleaks.toml


def test_caller_environment_cannot_allowlist(monkeypatch, tmp_path, capsys):
    """GITLEAKS_CONFIG, or a .gitleaksignore in the working directory holding the finding's exact fingerprint."""
    mod = load_scanner()
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "pkg-0.4-py3-none-any.whl").write_bytes(wheel({"pkg/b.py": f'key = "{fake_key()}"\n'}))
    allow_all = tmp_path / "allow-all.toml"
    allow_all.write_text("[extend]\nuseDefault = true\n[[allowlists]]\npaths = ['''.*''']\n")
    monkeypatch.setenv("GITLEAKS_CONFIG", str(allow_all))
    content = (tmp_path / "w").resolve() / f"run-{os.getpid()}" / "x" / "0000" / "content"
    (tmp_path / "cwd").mkdir()
    (tmp_path / "cwd" / ".gitleaksignore").write_text(f"{content / 'pkg' / 'b.py'}:aws-access-token:1\n")
    monkeypatch.chdir(tmp_path / "cwd")
    assert mod.main(["--local", str(tmp_path / "dist"), "--work", str(tmp_path / "w")]) == 1
    assert "pkg/b.py:1 [aws-access-token]" in capsys.readouterr().out


def test_files_gitleaks_does_not_read_fail_closed(tmp_path):
    """A lock file (default allowlist), a text file gitleaks takes for binary, a .pyc and a nested wheel."""
    key = fake_key()
    src = tmp_path / "m.py"
    src.write_text(f'KEY = "{key}"\n')
    pyc = Path(py_compile.compile(str(src), cfile=str(tmp_path / "m.pyc"))).read_bytes()
    with tarfile.open(tmp_path / "pkg-0.7.tar.gz", "w:gz") as t:
        add(t, "pkg-0.7/pkg/__init__.py", "x = 1\n")
        add(t, "pkg-0.7/Pipfile.lock", f'{{"aws_access_key_id": "{key}"}}\n')
        add(t, "pkg-0.7/.env", f"MZONE=eu\nAWS_ACCESS_KEY_ID={key}\n")
        add(t, "pkg-0.7/pkg/__pycache__/m.cpython-312.pyc", pyc)
        add(t, "pkg-0.7/vendor/dep-1.0-py3-none-any.whl", wheel({"dep/conf.py": f'key = "{key}"\n'}))
    src.unlink()
    (tmp_path / "m.pyc").unlink()
    r = scan("--local", tmp_path, "--work", tmp_path / "w")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "gitleaks did not read 4 files" in r.stderr
    for path in ("pkg-0.7/Pipfile.lock", "pkg-0.7/.env", "pkg-0.7/pkg/__pycache__/m.cpython-312.pyc",
                 "pkg-0.7/vendor/dep-1.0-py3-none-any.whl"):
        assert path in r.stderr
    assert key not in r.stdout + r.stderr


def test_archive_inside_a_package_is_scanned_and_fails_closed(tmp_path):
    key = fake_key()
    with tarfile.open(tmp_path / "pkg-0.5.tar.gz", "w:gz") as t:
        add(t, "pkg-0.5/tests/fixtures.zip", wheel({"conf/settings.py": f'aws_access_key_id = "{key}"\n'}))
    r = scan("--local", tmp_path, "--work", tmp_path / "w")
    assert r.returncode == 2, r.stdout + r.stderr  # gitleaks read its members, not the archive as a whole
    assert "pkg-0.5/tests/fixtures.zip!conf/settings.py" in r.stdout and key not in r.stdout + r.stderr
    assert "did not read 1 files" in r.stderr and "pkg-0.5/tests/fixtures.zip" in r.stderr


def test_unsafe_zip_is_refused(tmp_path):
    (tmp_path / "evil-0.1-py3-none-any.whl").write_bytes(wheel({"../../escaped.py": "x = 1\n"}))
    r = scan("--local", tmp_path, "--work", tmp_path / "w")
    assert r.returncode == 2 and "unsafe path" in r.stderr, r.stdout + r.stderr
    assert not list(tmp_path.rglob("escaped.py"))


def test_tar_extraction_is_safe(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    cases = {
        "dotdot": ([("p/../../escaped.py", "x = 1\n", tarfile.REGTYPE, "")], 2, "unsafe path"),
        "absolute": ([(str(outside / "abs.py"), "x = 1\n", tarfile.REGTYPE, "")], 2, "unsafe path"),
        "unknown-type": ([("p/odd.py", "", b"Z", "")], 2, "unknown type"),
        "links": ([("p/link", "", tarfile.SYMTYPE, str(outside)), ("p/link/through.py", "x = 1\n", tarfile.REGTYPE, ""),
                   ("p/hard.py", "", tarfile.LNKTYPE, "p/link/through.py"), ("p/fifo", "", tarfile.FIFOTYPE, "")],
                  0, ""),
    }
    for name, (members, rc, message) in cases.items():
        d = tmp_path / name
        d.mkdir()
        with tarfile.open(d / "pkg-0.6.tar.gz", "w:gz") as t:
            for member, data, kind, link in members:
                add(t, member, data, kind, link)
        r = scan("--local", d, "--work", tmp_path / "w")
        assert r.returncode == rc and message in r.stderr, (name, r.stdout + r.stderr)
    assert not list(outside.iterdir()) and not list(tmp_path.rglob("escaped.py"))


def test_duplicate_members_fail_closed(tmp_path):
    """The later copy would overwrite the earlier one on disk, hiding the key in it."""
    with tarfile.open(tmp_path / "pkg-0.8.tar.gz", "w:gz") as t:
        add(t, "pkg-0.8/pkg/a.py", f'key = "{fake_key()}"\n')
        add(t, "pkg-0.8/pkg/a.py", "x = 1\n")
    r = scan("--local", tmp_path, "--work", tmp_path / "w")
    assert r.returncode == 2 and "unpack to the same path" in r.stderr, r.stdout + r.stderr


def test_nothing_to_scan_is_an_error(tmp_path):
    (tmp_path / "dist").mkdir()
    r = scan("--local", tmp_path / "dist", "--work", tmp_path / "w")
    assert r.returncode == 2 and "nothing to scan" in r.stderr


def test_other_files_in_dist_fail_closed(tmp_path):
    """twine upload dist/* would send them too."""
    (tmp_path / "pkg-0.1-py3-none-any.whl").write_bytes(wheel({"pkg/__init__.py": "x = 1\n"}))
    (tmp_path / "pkg-0.1.win32.exe").write_bytes(b"MZ\x00\x00")
    r = scan("--local", tmp_path, "--work", tmp_path / "w")
    assert r.returncode == 2 and "pkg-0.1.win32.exe: not an archive" in r.stderr, r.stdout + r.stderr


def test_gitleaks_failure_fails_closed(tmp_path):
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "pkg-0.1-py3-none-any.whl").write_bytes(wheel({"pkg/__init__.py": "x = 1\n"}))
    for name, body, message in (("fails", "exit 1", "gitleaks failed"), ("silent", "exit 0", "no report")):
        fake = tmp_path / name
        fake.mkdir()
        (fake / "gitleaks").write_text(f"#!/bin/sh\n{body}\n")
        (fake / "gitleaks").chmod(0o755)
        env = {**os.environ, "PATH": f"{fake}{os.pathsep}{os.environ['PATH']}"}
        r = scan("--local", tmp_path / "dist", "--work", tmp_path / "w", env=env)
        assert r.returncode == 2 and message in r.stderr, (name, r.stdout + r.stderr)


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
    assert "| pkg | 1 | 1 | 1 | 0 |" in report and mod.NOT_TRIAGED in report
    assert key not in out.out + out.err + report


def test_report_keeps_triage(monkeypatch, tmp_path):
    mod = load_scanner()
    files = {"pkg-0.1-py3-none-any.whl": wheel({"pkg/a.py": f'key = "{fake_key()}"\n'})}
    fake_pypi(monkeypatch, mod, files)
    md, args = tmp_path / "report.md", ["pkg", "--work", str(tmp_path / "w"), "--markdown", str(tmp_path / "report.md")]
    assert mod.main(args) == 1
    md.write_text(md.read_text().replace(mod.NOT_TRIAGED, "Verdict: real, bead x-1. Was:"))
    assert mod.main(args) == 1
    assert "Verdict: real, bead x-1." in md.read_text() and mod.CHANGED not in md.read_text()
    files["pkg-0.2-py3-none-any.whl"] = wheel({"pkg/b.py": f'key = "{fake_key()}"\n'})
    fake_pypi(monkeypatch, mod, files)
    assert mod.main(args) == 1
    assert "Verdict: real, bead x-1." in md.read_text() and mod.CHANGED in md.read_text()


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
    fake_pypi(monkeypatch, mod, {})  # a package PyPI knows but with no files
    assert mod.main(["pkg", "--work", str(tmp_path / "w3")]) == 2
    assert "PyPI lists no files" in capsys.readouterr().err
