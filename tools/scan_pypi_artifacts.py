#!/usr/bin/env python3
"""Secret scan of what users actually download from PyPI (vps-eht).

vps-v9s scans git history, but an sdist or wheel is built from the working tree and can carry files that were never
committed (.env, credentials, notebooks with output). This downloads every file of every release listed by the PyPI
JSON API, checks its sha256, unpacks it without running anything (no setup.py, no pip), and runs `gitleaks dir` (the
gitleaks 8.19+ name for `gitleaks detect --no-git`) over the unpacked tree. Findings are printed as
package/version/file :: path:line [rule] only: gitleaks runs with --redact and the secret value is never printed.

A file counts as scanned only if gitleaks read it: a path-only coverage rule fires once for every file gitleaks reads,
and any other non-empty file fails the run (exit 2) with its path listed. That catches what gitleaks skips without a
word: files that look binary to it (even a text file starting "MZ"), archives inside the package (their members are
still scanned and reported, but the archive itself fails), paths on its default allowlist (lock files, .git/, venvs,
office documents), and compiled .pyc files, which it reads but whose marshal bytes break its word-boundary matches.
Also:
  * the default allowlist skips every `*.dist-info/` path, which in a wheel holds METADATA (the README): those
    directories are renamed `*.dist-info.unpacked` in the scratch copy so they are read;
  * the archive is unpacked one level below the scan root, the default rules are forced with --config and no
    .gitleaksignore is read, so neither the package nor the caller's environment (GITLEAKS_CONFIG, a .gitleaksignore in
    the working directory) can allowlist a secret, and `gitleaks:allow` comments are not honoured;
  * members with unsafe or colliding paths, or of an unknown tar type, fail the file instead of being skipped.
Not scanned: zip and tar metadata (archive comments, pax headers).

  tools/scan_pypi_artifacts.py villaProductSdk lambdasdk ...      scan PyPI (needs network)
  tools/scan_pypi_artifacts.py --local DIR                         scan every file in DIR, e.g. dist/ before upload
  --work DIR    keep downloads here and reuse those whose sha256 still matches (default: a temp dir, removed at exit)
  --markdown F  also write a report: every file checked and each finding as path:line [rule]; a Triage section
                already in F is kept, with a warning when the findings changed since it was written

Exit 0 = no findings; 1 = findings; 2 = something was not scanned (gitleaks missing or failing, nothing to scan, a
listing, download, checksum or unpack failure, a file gitleaks did not read): no file is counted clean unless read.
Needs gitleaks 8.19+ and a Python with tarfile extraction filters (3.12, or 3.8.17/3.9.17/3.10.12/3.11.4 and later).
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
import unicodedata
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ZIP_SUFFIXES = (".zip", ".whl", ".egg")
TAR_SUFFIXES = (".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".tar")
ARCHIVE_SUFFIXES = ZIP_SUFFIXES + TAR_SUFFIXES
UNHIDE = ".unpacked"  # appended to *.dist-info dir names, which gitleaks' default allowlist would skip
UNRELIABLE = (".pyc", ".pyo")  # gitleaks reads them, but marshal type bytes break its word-boundary matches
COVERAGE_RULE = "scan-coverage"
GITLEAKS_CONFIG = f"""[extend]
useDefault = true

[[rules]]
id = "{COVERAGE_RULE}"
description = "fires once for every file gitleaks reads, so a file it skipped is never counted as scanned"
path = '''.*'''
"""
MAX_ARCHIVE_DEPTH = "5"
NOT_TRIAGED = "Not triaged yet:"
NO_FINDINGS = "No findings, nothing to triage."
CHANGED = "**The findings changed since this triage was written: check every verdict against the tables below.**"


def printable(s):
    """Names come from the archives: never send their control characters raw to a terminal or a report."""
    return re.sub(r"[\x00-\x1f\x7f]", lambda m: f"\\x{ord(m.group()):02x}", str(s))


def check_members(names, file_names):
    """Refuse absolute paths and '..', and two files that unpack to the same path (the later would hide the other)."""
    for name in names:
        p = PurePosixPath(name)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError(f"unsafe path in archive: {name!r}")
    seen = set()
    for name in file_names:
        key = unicodedata.normalize("NFC", str(PurePosixPath(name))).casefold()  # also on case-insensitive disks
        if key in seen:
            raise ValueError(f"two members unpack to the same path: {name!r}")
        seen.add(key)


def unpack(archive: Path, dest: Path):
    dest.mkdir(parents=True)
    name = archive.name.lower()
    if name.endswith(ZIP_SUFFIXES):
        with zipfile.ZipFile(archive) as z:
            infos = z.infolist()
            check_members([i.filename for i in infos], [i.filename for i in infos if not i.is_dir()])
            z.extractall(dest)
    elif name.endswith(TAR_SUFFIXES):
        with tarfile.open(archive) as t:
            members = t.getmembers()
            odd = [m.name for m in members if m.type not in tarfile.SUPPORTED_TYPES]
            if odd:  # GNU tar would unpack these as regular files
                raise ValueError(f"tar member of unknown type: {odd[0]!r}")
            check_members([m.name for m in members], [m.name for m in members if m.isfile()])
            data = [m for m in members if m.isfile() or m.isdir()]  # links, devices, fifos hold no data of their own
            t.extractall(dest, members=data, filter="data")
    else:
        raise ValueError(f"not an archive this scanner knows: {archive.name!r}")


def unhide_dist_info(tree: Path):
    """Rename *.dist-info dirs so gitleaks reads them; return the number of files in tree."""
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
                raise ValueError(f"unexpected download URL from PyPI for {name!r}")
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
    part = dest.with_name(f"{dest.name}.{os.getpid()}.part")
    try:
        with urllib.request.urlopen(url, timeout=120) as r, open(part, "wb") as out:
            shutil.copyfileobj(r, out)
        if sha256_of(part) != sha256:
            raise ValueError(f"sha256 mismatch for {dest.name}")
        part.replace(dest)
    finally:
        part.unlink(missing_ok=True)


def gitleaks(tree: Path, content: Path, run: Path):
    """Scan tree, whose only entry is content. Return (findings, read): sorted [(path in content, line, rule id)] and
    the set of paths in content that gitleaks read."""
    report, quiet = run / "report.json", run / "empty"
    report.unlink(missing_ok=True)
    r = subprocess.run(
        ["gitleaks", "dir", "--redact", "--no-banner", "--no-color", "--log-level", "error", "--exit-code", "0",
         "--config", str(run / "gitleaks.toml"), "--gitleaks-ignore-path", str(quiet), "--ignore-gitleaks-allow",
         "--max-archive-depth", MAX_ARCHIVE_DEPTH, "--report-format", "json", "--report-path", str(report), str(tree)],
        capture_output=True, text=True, cwd=quiet,
    )
    if r.returncode != 0:
        raise RuntimeError(f"gitleaks failed: {printable(r.stderr.strip()[:300])}")
    text = report.read_text() if report.exists() else ""
    report.unlink(missing_ok=True)
    if not text.strip():
        raise RuntimeError("gitleaks wrote no report")
    findings, read = set(), set()
    prefix = str(content) + os.sep
    for f in json.loads(text):
        path = f["File"][len(prefix):] if f["File"].startswith(prefix) else f["File"]
        if f["RuleID"] == COVERAGE_RULE:
            read.add(path)
        else:
            path = re.sub(r"(?i)(\.dist-info)" + re.escape(UNHIDE) + "/", r"\1/", path)
            findings.add((path, f["StartLine"], f["RuleID"]))
    return sorted(findings), read


def unread_files(content: Path, read):
    """Non-empty files gitleaks did not read, and compiled files it cannot match reliably."""
    out = []
    for root, _, files in os.walk(content):
        for name in files:
            p = Path(root, name)
            rel = str(p.relative_to(content))
            if p.stat().st_size and (rel not in read or name.lower().endswith(UNRELIABLE)):
                out.append(re.sub(r"(?i)(\.dist-info)" + re.escape(UNHIDE) + "/", r"\1/", rel))
    return sorted(out)


def cell(s):
    """Keep names from the archives from breaking the Markdown table."""
    return printable(s).replace("|", "\\|").replace("`", "'")


def findings_digest(rows):
    lines = sorted(f"{r[0]}|{r[1]}|{r[2]}|{p}|{line}|{rule}" for r in rows for p, line, rule in r[6])
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()[:16]


def previous_triage(path: Path):
    """(triage text, findings digest) of an earlier report at path, or None if it has no triage written in it."""
    try:
        text = path.read_text()
    except FileNotFoundError:
        return None
    m = re.search(r"^## Triage\n\n(.*?)\n\n## Totals\n", text, re.S | re.M)
    if not m or m.group(1).startswith((NOT_TRIAGED, NO_FINDINGS)):
        return None
    d = re.search(r"^<!-- findings digest: (\w+) -->$", text, re.M)
    return m.group(1).removeprefix(CHANGED + "\n\n"), d.group(1) if d else ""


def write_markdown(path: Path, rows, listing_errors, sources, packages):
    version = subprocess.run(["gitleaks", "version"], capture_output=True, text=True).stdout.strip()
    when = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    n_find = sum(len(r[6]) for r in rows)
    errors = len(listing_errors) + sum(1 for r in rows if r[4] != "ok")
    digest = findings_digest(rows)
    triage = NO_FINDINGS if not n_find else (
        f"{NOT_TRIAGED} give each finding a verdict, a bead for each real one or the reason it is a false positive.")
    kept = previous_triage(path) if n_find else None
    if kept:
        triage = kept[0] if kept[1] == digest else f"{CHANGED}\n\n{kept[0]}"
    lines = [
        "# PyPI artifact secret scan",
        "",
        "<!-- written by tools/scan_pypi_artifacts.py (vps-eht); a re-run rewrites the tables and keeps the Triage -->",
        f"<!-- findings digest: {digest} -->",
        "",
        f"- Scanned: {when} with gitleaks {version}, default rules (`gitleaks dir --redact`).",
        f"- Source: {sources}.",
        f"- Result: {len(rows)} files ({sum(r[5] for r in rows)} files inside them), {n_find} findings, {errors} "
        "errors. A finding is shown as path:line [rule] only; secret values are never written here.",
        "- Each file was checked against its sha256 and unpacked without running anything. Every non-empty file inside "
        "it counts as scanned only if gitleaks read it (a coverage rule fires per file read); a file it did not read "
        "(binary-looking, compiled, an archive inside the package, a path on its default allowlist) is an error. "
        "`*.dist-info/` (wheel METADATA) is read; `gitleaks:allow` comments and any `.gitleaks.toml` or "
        "`.gitleaksignore` shipped in the package or set in the caller's environment are ignored.",
        "",
        "## Triage",
        "",
        triage,
        "",
        "## Totals",
        "",
        "| package | versions | files | findings | errors |",
        "|---|---|---|---|---|",
    ]
    for pkg in packages:
        mine = [r for r in rows if r[0] == pkg]
        n_err = sum(1 for r in mine if r[4] != "ok") + sum(1 for p, _ in listing_errors if p == pkg)
        lines.append(f"| {cell(pkg)} | {len({r[1] for r in mine})} | {len(mine)} | {sum(len(r[6]) for r in mine)} "
                     f"| {n_err} |")
    if listing_errors:
        lines += ["", "Packages whose file list could not be read (nothing of them was scanned):", ""]
        lines += [f"- {cell(pkg)}: {cell(msg)}" for pkg, msg in listing_errors]
    lines += ["", "## Every file checked", "",
              "| package | version | file | sha256 (first 12) | files inside | status | findings (path:line [rule]) |",
              "|---|---|---|---|---|---|---|"]
    for pkg, version, filename, sha, status, n_inside, findings in rows:
        f = "<br>".join(f"`{cell(p)}:{line}` [{cell(rule)}]" for p, line, rule in findings) or "none"
        lines.append(f"| {cell(pkg)} | {cell(version)} | {cell(filename)} | {(sha or '-')[:12]} | {n_inside} "
                     f"| {cell(status)} | {f} |")
    path.write_text("\n".join(lines) + "\n")


def scan(a, work: Path, run: Path):
    rows = []  # (package, version, file, sha256, status, files inside, findings); status "ok" or "error: why"
    listing_errors = []  # (package, why)
    items = []  # (package, version, file, url, sha256)
    if a.local:
        for p in sorted(a.local.iterdir()):
            if p.resolve() == work:  # our own --work dir, not something to upload
                continue
            if p.is_file() and p.name.lower().endswith(ARCHIVE_SUFFIXES):
                items.append(("local", "-", p.name, None, sha256_of(p)))
            else:  # `twine upload dist/*` would send it too
                print(f"ERROR local {printable(p.name)}: not an archive this scanner knows", file=sys.stderr)
                rows.append(("local", "-", p.name, None, "error: not an archive this scanner knows", 0, []))
    for pkg in a.packages:
        try:
            files = pypi_files(pkg)
            if not files:
                raise ValueError("PyPI lists no files")
            items += [(pkg, v, fn, url, sha) for v, fn, url, sha in files]
        except Exception as e:  # e.g. network, unknown package, changed API: the package was not scanned
            print(f"ERROR {pkg}: cannot list its PyPI files: {printable(e)}", file=sys.stderr)
            listing_errors.append((pkg, f"cannot list its PyPI files: {e}"))
    if not items and not rows and not listing_errors:
        print("scan_pypi_artifacts: nothing to scan", file=sys.stderr)
        return 2
    for i, (pkg, version, filename, url, sha) in enumerate(items):
        archive = (a.local / filename) if a.local else work / "dl" / pkg / filename
        tree = run / "x" / f"{i:04d}"
        content = tree / "content"
        try:
            if url:
                archive.parent.mkdir(parents=True, exist_ok=True)
                download(url, sha, archive)
            unpack(archive, content)
            n_inside = unhide_dist_info(content)
            findings, read = gitleaks(tree, content, run)
            unread = unread_files(content, read)
        except Exception as e:  # report and keep scanning the rest; exit 2 at the end
            print(f"ERROR {pkg} {version} {printable(filename)}: {printable(e)}", file=sys.stderr)
            rows.append((pkg, version, filename, sha, f"error: {e}"[:160], 0, []))
            continue
        finally:
            shutil.rmtree(tree, ignore_errors=True)
        status = "ok"
        if unread:
            status = f"error: gitleaks did not read {len(unread)} files: " + ", ".join(unread[:3])[:200]
            print(f"ERROR {pkg} {version} {printable(filename)}: gitleaks did not read {len(unread)} files (binary, "
                  "compiled, archive or default-allowlisted path): " + ", ".join(printable(u) for u in unread[:10]),
                  file=sys.stderr)
        rows.append((pkg, version, filename, sha, status, n_inside, findings))
        for path, line, rule in findings:
            print(f"FINDING {pkg} {version} {printable(filename)} :: {printable(path)}:{line} [{rule}]", flush=True)
    n_find = sum(len(r[6]) for r in rows)
    errors = len(listing_errors) + sum(1 for r in rows if r[4] != "ok")
    print(f"scan_pypi_artifacts: {len(rows)} files checked, {n_find} findings, {errors} errors")
    if a.markdown:
        sources = (f"every file in {a.local}" if a.local else
                   "every file of every release on PyPI of " + ", ".join(a.packages))
        write_markdown(a.markdown, rows, listing_errors, sources, a.packages or ["local"])
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
    tmp = run = None
    try:
        if a.work:
            work = a.work.resolve()
            work.mkdir(parents=True, exist_ok=True)
        else:
            tmp = tempfile.mkdtemp(prefix="pypi-scan-")
            work = Path(tmp)
        run = work / f"run-{os.getpid()}"  # per run: concurrent runs can share --work and its downloads
        shutil.rmtree(run, ignore_errors=True)
        (run / "empty").mkdir(parents=True)
        (run / "gitleaks.toml").write_text(GITLEAKS_CONFIG)
        return scan(a, work, run)
    except Exception as e:  # anything unexpected is a setup error, never "clean" (0) or "findings" (1)
        print(f"scan_pypi_artifacts: {type(e).__name__}: {printable(e)}", file=sys.stderr)
        return 2
    finally:
        if run:
            shutil.rmtree(run, ignore_errors=True)
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
