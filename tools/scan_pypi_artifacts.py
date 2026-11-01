#!/usr/bin/env python3
"""Secret scan of what users actually download from PyPI (vps-eht).

vps-v9s scans git history, but an sdist or wheel is built from the working tree and can carry files that were never
committed (.env, credentials, notebooks with output). This downloads every file of every release listed by the PyPI
JSON API, checks its sha256, unpacks it without running anything (no setup.py, no pip), and runs gitleaks over the
unpacked tree. Findings are printed as package/version/file/path/rule only: gitleaks runs with --redact and the
secret value is never read back or printed.

  tools/scan_pypi_artifacts.py villaProductSdk lambdasdk ...      scan PyPI (needs network)
  tools/scan_pypi_artifacts.py --local DIR                         scan the .tar.gz/.zip/.whl files in DIR (tests)
  --work DIR    keep downloads and unpacked trees here (default: a temp dir, removed at exit)
  --markdown F  also write a per-file table to F

Exit 0 = no findings; 1 = findings; 2 = setup error (gitleaks missing, download or checksum failure).
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ARCHIVE_SUFFIXES = (".tar.gz", ".tgz", ".tar.bz2", ".zip", ".whl", ".egg")


def safe_members(names):
    """Refuse absolute paths and '..' so an archive cannot write outside its own directory."""
    for name in names:
        p = PurePosixPath(name)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError(f"unsafe path in archive: {name!r}")


def unpack(archive: Path, dest: Path):
    dest.mkdir(parents=True)
    name = archive.name.lower()
    if name.endswith((".zip", ".whl", ".egg")):
        with zipfile.ZipFile(archive) as z:
            safe_members(z.namelist())
            z.extractall(dest)
    elif name.endswith((".tar.gz", ".tgz", ".tar.bz2")):
        with tarfile.open(archive) as t:
            members = [m for m in t.getmembers() if m.isfile() or m.isdir()]  # no links, devices or fifos
            safe_members(m.name for m in members)
            t.extractall(dest, members=members, filter="data")
    else:
        raise ValueError(f"not an archive this scanner knows: {archive.name}")


def pypi_files(package):
    with urllib.request.urlopen(f"https://pypi.org/pypi/{package}/json", timeout=60) as r:
        data = json.load(r)
    for version, files in data["releases"].items():
        for f in files:
            yield version, f["filename"], f["url"], f["digests"]["sha256"]


def download(url, sha256, dest: Path):
    h = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=120) as r, open(dest, "wb") as out:
        for chunk in iter(lambda: r.read(1 << 16), b""):
            h.update(chunk)
            out.write(chunk)
    if h.hexdigest() != sha256:
        raise ValueError(f"sha256 mismatch for {dest.name}")


def gitleaks(tree: Path, report: Path):
    """Return [(relative path, rule id)] for each finding in tree."""
    r = subprocess.run(
        ["gitleaks", "dir", "--redact", "--no-banner", "--log-level", "error", "--exit-code", "0",
         "--report-format", "json", "--report-path", str(report), str(tree)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"gitleaks failed on {tree.name}: {r.stderr.strip()[:300]}")
    found = json.loads(report.read_text() or "[]")
    report.unlink()
    out = []
    for f in found:
        path = Path(f["File"])
        try:
            path = path.relative_to(tree)
        except ValueError:
            pass
        out.append((str(path), f["RuleID"]))
    return sorted(set(out))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("packages", nargs="*")
    ap.add_argument("--local", type=Path)
    ap.add_argument("--work", type=Path)
    ap.add_argument("--markdown", type=Path)
    a = ap.parse_args(argv)
    if not shutil.which("gitleaks"):
        print("scan_pypi_artifacts: gitleaks is not installed", file=sys.stderr)
        return 2
    if bool(a.local) == bool(a.packages):
        ap.error("give package names or --local DIR, not both")

    tmp = None
    if a.work:
        work = a.work
        work.mkdir(parents=True, exist_ok=True)
    else:
        tmp = tempfile.mkdtemp(prefix="pypi-scan-")
        work = Path(tmp)
    rows, errors = [], 0
    try:
        if a.local:
            items = [("local", "-", p.name, None, None) for p in sorted(a.local.iterdir())
                     if p.name.lower().endswith(ARCHIVE_SUFFIXES)]
        else:
            items = [(pkg, v, fn, url, sha) for pkg in a.packages for v, fn, url, sha in pypi_files(pkg)]
        for i, (pkg, version, filename, url, sha) in enumerate(items):
            archive = (a.local / filename) if a.local else work / "dl" / pkg / filename
            tree = work / "x" / f"{i:04d}-{filename}"
            try:
                if url:
                    archive.parent.mkdir(parents=True, exist_ok=True)
                    if not archive.exists():
                        download(url, sha, archive)
                if tree.exists():
                    shutil.rmtree(tree)
                unpack(archive, tree)
                findings = gitleaks(tree, work / "report.json")
            except Exception as e:  # report and keep scanning the rest; exit 2 at the end
                errors += 1
                print(f"ERROR {pkg} {version} {filename}: {e}", file=sys.stderr)
                rows.append((pkg, version, filename, "error", []))
                continue
            finally:
                if tree.exists():
                    shutil.rmtree(tree)
            rows.append((pkg, version, filename, "ok", findings))
            for path, rule in findings:
                print(f"FINDING {pkg} {version} {filename} :: {path} [{rule}]")
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)

    n_find = sum(len(r[4]) for r in rows)
    print(f"scan_pypi_artifacts: {len(rows)} files scanned, {n_find} findings, {errors} errors")
    if a.markdown:
        lines = ["| package | version | file | status | findings (path [rule]) |", "|---|---|---|---|---|"]
        for pkg, version, filename, status, findings in rows:
            f = "<br>".join(f"`{p}` [{r}]" for p, r in findings) or "none"
            lines.append(f"| {pkg} | {version} | {filename} | {status} | {f} |")
        a.markdown.write_text("\n".join(lines) + "\n")
    if errors:
        return 2
    return 1 if n_find else 0


if __name__ == "__main__":
    sys.exit(main())
