#!/usr/bin/env python3
"""Secret scan of what users actually download from PyPI (vps-eht).

vps-v9s scans git history, but an sdist or wheel is built from the working tree and can carry files that were never
committed (.env, credentials, notebooks with output). This downloads every file of every release listed by the PyPI
JSON API, checks its sha256, unpacks it without running anything (no setup.py, no pip), and runs `gitleaks dir` (the
gitleaks 8.19+ name for `gitleaks detect --no-git`) over the unpacked tree. Findings are printed as
package/version/file :: path:line [rule] only: gitleaks runs with --redact and the secret value is never printed.

gitleaks defaults that would hide part of a published file are turned off:
  * the default allowlist skips every `*.dist-info/` path, which in a wheel holds METADATA (the README): those
    directories are renamed `*.dist-info.unpacked` in the scratch copy so they are scanned;
  * a `.gitleaks.toml` or `.gitleaksignore` shipped in a package could allowlist its own secrets: the default rules
    are forced with --config, no ignore file is read, and the archive is unpacked one level below the scan root;
  * `gitleaks:allow` comments are not honoured, and archives inside a package are scanned too.

  tools/scan_pypi_artifacts.py villaProductSdk lambdasdk ...      scan PyPI (needs network)
  tools/scan_pypi_artifacts.py --local DIR                         scan the archives in DIR, e.g. dist/ before upload
  --work DIR    keep downloads here and reuse those whose sha256 still matches (default: a temp dir, removed at exit)
  --markdown F  also write a report listing every file scanned and each finding as path:line [rule]

Exit 0 = no findings; 1 = findings; 2 = setup error (gitleaks missing, nothing to scan, or a listing, download,
checksum or unpack failure: a file that could not be scanned is never counted as clean).
Needs gitleaks 8.19+ and a Python with tarfile extraction filters (3.12, or 3.8.17/3.9.17/3.10.12/3.11.4 and later);
without them every file fails to unpack and the run exits 2.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ZIP_SUFFIXES = (".zip", ".whl", ".egg")
TAR_SUFFIXES = (".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".tar")
ARCHIVE_SUFFIXES = ZIP_SUFFIXES + TAR_SUFFIXES
UNHIDE = ".unpacked"  # appended to *.dist-info dir names, which gitleaks' default allowlist would skip
GITLEAKS_CONFIG = "[extend]\nuseDefault = true\n"  # gitleaks' own default rules and allowlists, nothing added
MAX_ARCHIVE_DEPTH = "5"


def safe_members(names):
    """Refuse absolute paths and '..' so an archive cannot write outside its own directory."""
    for name in names:
        p = PurePosixPath(name)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError(f"unsafe path in archive: {name!r}")


def unpack(archive: Path, dest: Path):
    dest.mkdir(parents=True)
    name = archive.name.lower()
    if name.endswith(ZIP_SUFFIXES):
        with zipfile.ZipFile(archive) as z:
            safe_members(z.namelist())
            z.extractall(dest)
    elif name.endswith(TAR_SUFFIXES):
        with tarfile.open(archive) as t:
            members = [m for m in t.getmembers() if m.isfile() or m.isdir()]  # no links, devices or fifos
            safe_members(m.name for m in members)
            t.extractall(dest, members=members, filter="data")
    else:
        raise ValueError(f"not an archive this scanner knows: {archive.name}")


def unhide_dist_info(tree: Path):
    """Rename *.dist-info dirs so gitleaks scans them; return the number of files in tree."""
    n = 0
    for root, dirs, files in os.walk(tree):
        n += len(files)
        for i, d in enumerate(dirs):
            if d.lower().endswith(".dist-info"):
                os.rename(os.path.join(root, d), os.path.join(root, d + UNHIDE))
                dirs[i] = d + UNHIDE
    return n


def pypi_files(package):
    """[(version, filename, url, sha256)] for every file of every release in the PyPI JSON API."""
    with urllib.request.urlopen(f"https://pypi.org/pypi/{package}/json", timeout=60) as r:
        data = json.load(r)
    out = []
    for version, files in data["releases"].items():
        for f in files:
            name, url = f["filename"], f["url"]
            if "/" in name or "\\" in name or name in ("", ".", ".."):
                raise ValueError(f"unexpected file name from PyPI: {name!r}")
            if not url.startswith("https://"):
                raise ValueError(f"unexpected download URL from PyPI for {name}")
            out.append((version, name, url, f["digests"]["sha256"]))
    return out


def sha256_of(path: Path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url, sha256, dest: Path):
    """Fetch url to dest unless dest already has PyPI's sha256; a file that does not match is never kept."""
    if dest.exists() and sha256_of(dest) == sha256:
        return
    part = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(url, timeout=120) as r, open(part, "wb") as out:
        shutil.copyfileobj(r, out)
    if sha256_of(part) != sha256:
        part.unlink()
        raise ValueError(f"sha256 mismatch for {dest.name}")
    part.replace(dest)


def gitleaks(tree: Path, content: Path, work: Path):
    """Scan tree, whose only entry is content; return sorted [(path in content, line, rule id)]."""
    report, quiet = work / "report.json", work / "empty"
    r = subprocess.run(
        ["gitleaks", "dir", "--redact", "--no-banner", "--no-color", "--log-level", "error", "--exit-code", "0",
         "--config", str(work / "gitleaks.toml"), "--gitleaks-ignore-path", str(quiet), "--ignore-gitleaks-allow",
         "--max-archive-depth", MAX_ARCHIVE_DEPTH, "--report-format", "json", "--report-path", str(report), str(tree)],
        capture_output=True, text=True, cwd=quiet,
    )
    if r.returncode != 0:
        raise RuntimeError(f"gitleaks failed: {r.stderr.strip()[:300]}")
    found = json.loads(report.read_text() or "[]")
    report.unlink()
    out = set()
    for f in found:
        path = f["File"]
        if path.startswith(str(content) + os.sep):
            path = path[len(str(content)) + 1:]
        path = re.sub(r"(?i)(\.dist-info)" + re.escape(UNHIDE) + "/", r"\1/", path)
        out.add((path, f["StartLine"], f["RuleID"]))
    return sorted(out)


def cell(s):
    """Path and file names come from the archives: keep them from breaking the Markdown table."""
    return str(s).replace("|", "\\|").replace("`", "'")


def write_markdown(path: Path, rows, sources, errors):
    version = subprocess.run(["gitleaks", "version"], capture_output=True, text=True).stdout.strip()
    when = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    n_find = sum(len(r[6]) for r in rows)
    lines = [
        "# PyPI artifact secret scan",
        "",
        "<!-- written by tools/scan_pypi_artifacts.py (vps-eht); a re-run replaces this file, Triage included -->",
        "",
        f"- Scanned: {when} with gitleaks {version}, default rules (`gitleaks dir --redact`).",
        f"- Source: {sources}.",
        f"- Result: {len(rows)} files ({sum(r[5] for r in rows)} files inside them), {n_find} findings, {errors} "
        "errors. A finding is shown as path:line [rule] only; secret values are never written here.",
        "- Each file was checked against its sha256, unpacked without running anything and scanned in full: "
        "`*.dist-info/` (wheel METADATA) and archives inside the package included, `gitleaks:allow` comments and any "
        "`.gitleaks.toml` or `.gitleaksignore` shipped in the package ignored.",
        "",
        "## Triage",
        "",
        "Not triaged yet: give each finding a verdict, a bead for each real one or the reason it is a false positive."
        if n_find else "No findings, nothing to triage.",
        "",
        "## Totals",
        "",
        "| package | versions | files | findings | errors |",
        "|---|---|---|---|---|",
    ]
    for pkg in dict.fromkeys(r[0] for r in rows):
        mine = [r for r in rows if r[0] == pkg]
        lines.append(f"| {pkg} | {len({r[1] for r in mine})} | {len(mine)} | {sum(len(r[6]) for r in mine)} | "
                     f"{sum(1 for r in mine if r[4] == 'error')} |")
    lines += ["", "## Every file scanned", "",
              "| package | version | file | sha256 (first 12) | files inside | status | findings (path:line [rule]) |",
              "|---|---|---|---|---|---|---|"]
    for pkg, version, filename, sha, status, n_inside, findings in rows:
        f = "<br>".join(f"`{cell(p)}:{line}` [{cell(rule)}]" for p, line, rule in findings) or "none"
        lines.append(f"| {cell(pkg)} | {cell(version)} | {cell(filename)} | {(sha or '-')[:12]} | {n_inside} "
                     f"| {status} | {f} |")
    path.write_text("\n".join(lines) + "\n")


def scan(a, work: Path):
    (work / "gitleaks.toml").write_text(GITLEAKS_CONFIG)
    shutil.rmtree(work / "empty", ignore_errors=True)
    (work / "empty").mkdir()
    rows, errors = [], 0  # rows: (package, version, file, sha256, status, files inside, findings)
    items = []  # (package, version, file, url, sha256)
    if a.local:
        items = [("local", "-", p.name, None, sha256_of(p)) for p in sorted(a.local.iterdir())
                 if p.name.lower().endswith(ARCHIVE_SUFFIXES)]
    for pkg in a.packages:
        try:
            items += [(pkg, v, fn, url, sha) for v, fn, url, sha in pypi_files(pkg)]
        except Exception as e:  # e.g. network, unknown package, changed API: the package was not scanned
            errors += 1
            print(f"ERROR {pkg}: cannot list its PyPI files: {e}", file=sys.stderr)
            rows.append((pkg, "-", "(file list)", None, "error", 0, []))
    if not items and not errors:
        print("scan_pypi_artifacts: nothing to scan", file=sys.stderr)
        return 2
    for i, (pkg, version, filename, url, sha) in enumerate(items):
        archive = (a.local / filename) if a.local else work / "dl" / pkg / filename
        tree = work / "x" / f"{i:04d}"
        content = tree / "content"
        try:
            if url:
                archive.parent.mkdir(parents=True, exist_ok=True)
                download(url, sha, archive)
            if tree.exists():
                shutil.rmtree(tree)
            unpack(archive, content)
            n_inside = unhide_dist_info(content)
            findings = gitleaks(tree, content, work)
        except Exception as e:  # report and keep scanning the rest; exit 2 at the end
            errors += 1
            print(f"ERROR {pkg} {version} {filename}: {e}", file=sys.stderr)
            rows.append((pkg, version, filename, sha, "error", 0, []))
            continue
        finally:
            if tree.exists():
                shutil.rmtree(tree)
        rows.append((pkg, version, filename, sha, "ok", n_inside, findings))
        for path, line, rule in findings:
            print(f"FINDING {pkg} {version} {filename} :: {path}:{line} [{rule}]", flush=True)  # live in long runs
    n_find = sum(len(r[6]) for r in rows)
    print(f"scan_pypi_artifacts: {len(rows)} files scanned, {n_find} findings, {errors} errors")
    if a.markdown:
        sources = (f"the archives in {a.local}" if a.local else
                   "every file of every release on PyPI of " + ", ".join(a.packages))
        write_markdown(a.markdown, rows, sources, errors)
    if errors:
        return 2
    return 1 if n_find else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("packages", nargs="*")
    ap.add_argument("--local", type=Path)
    ap.add_argument("--work", type=Path)
    ap.add_argument("--markdown", type=Path)
    a = ap.parse_args(argv)
    if bool(a.local) == bool(a.packages):
        ap.error("give package names or --local DIR, not both")
    if not shutil.which("gitleaks"):
        print("scan_pypi_artifacts: gitleaks is not installed", file=sys.stderr)
        return 2
    tmp = None if a.work else tempfile.mkdtemp(prefix="pypi-scan-")
    work = a.work.resolve() if a.work else Path(tmp)
    try:
        work.mkdir(parents=True, exist_ok=True)
        return scan(a, work)
    except Exception as e:  # anything unexpected is a setup error, never "clean" (0) or "findings" (1)
        print(f"scan_pypi_artifacts: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
