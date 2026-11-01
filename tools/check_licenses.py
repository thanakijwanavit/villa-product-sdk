#!/usr/bin/env python3
"""License inventory of the SDK's runtime dependency closure (vps-b5i).

Starts from settings.ini's `requirements` line (or --requirements), walks each package's Requires-Dist through
importlib.metadata (extras and requirements whose environment markers do not match are skipped), and reads each
package's License-Expression, then License, then its "License ::" classifiers. Only that closure is reported, never
every installed distribution (uv's Python on G1 also sees system dist-packages such as python-apt, which are GPL and
not ours). Writes a markdown table (name, version, license) to --output and exits 1 when a license is GPL, AGPL,
LGPL or SSPL, or is empty/unknown and not listed in tools/license-allowlist.txt ("name: reason" per line).

  python tools/check_licenses.py --output THIRD_PARTY_LICENSES.md
"""
from __future__ import annotations

import argparse
import configparser
import re
import sys
from importlib import metadata
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parent.parent
BLOCKED = re.compile(r"\b(A?GPL|LGPL|SSPL|GNU (Affero |Lesser |Library )?General Public)", re.I)
UNKNOWN = {"", "unknown", "none", "other/proprietary license", "dual license"}


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_names(line: str) -> list[str]:
    """'dataclasses-json boto3 urllib3==1.25.10' -> names, without versions or extras."""
    return [re.split(r"[\s\[<>=!~;(]", item, maxsplit=1)[0] for item in line.split() if item.strip()]


def parse_requires(spec: str) -> tuple[str, str | None]:
    """'urllib3 (<1.27,>=1.21.1) ; extra == "socks"' -> ('urllib3', 'extra == "socks"')."""
    head, _, marker = spec.partition(";")
    name = re.split(r"[\s\[<>=!~(]", head.strip(), maxsplit=1)[0]
    return name, (marker.strip() or None)


def marker_applies(marker: str | None) -> bool:
    if not marker:
        return True
    if "extra" in marker:
        return False  # optional extras are not part of the runtime closure
    try:
        from packaging.markers import Marker
    except ImportError:  # without packaging, keep it: reporting one package too many is the safe side
        return True
    try:
        return Marker(marker).evaluate()
    except Exception:
        return True


def closure(roots: Iterable[str], requires: Callable[[str], list[str] | None]) -> list[str]:
    """Names reachable from roots. `requires(name)` gives a package's Requires-Dist, or None if not installed."""
    seen: dict[str, str] = {}
    stack = list(roots)
    while stack:
        name = stack.pop()
        key = normalize(name)
        if key in seen:
            continue
        deps = requires(name)
        if deps is None:
            continue  # not installed here: the inventory covers what this environment would ship
        seen[key] = name
        for spec in deps:
            dep, marker = parse_requires(spec)
            if marker_applies(marker):
                stack.append(dep)
    return sorted(seen.values(), key=normalize)


def license_of(meta) -> str:
    expression = (meta.get("License-Expression") or "").strip()
    if expression:
        return expression
    text = (meta.get("License") or "").strip()
    if text and len(text) < 120 and "\n" not in text and text.lower() not in UNKNOWN:
        return text  # a vague value ("Dual License", python-dateutil) falls through to the classifiers
    classifiers = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
    classifiers = [c for c in classifiers if c != "OSI Approved"]
    if classifiers:
        return " / ".join(classifiers)
    return text.splitlines()[0][:80] if text else ""


def classify(name: str, license_text: str, allowlist: dict[str, str]) -> tuple[bool, str]:
    """(ok, why). GPL-family licenses always fail; an empty or unknown one passes only when allowlisted."""
    if BLOCKED.search(license_text):
        return False, f"{license_text}: copyleft license not allowed in an Apache-2.0 release"
    if license_text.strip().lower() in UNKNOWN:
        if normalize(name) in allowlist:
            return True, f"allowlisted: {allowlist[normalize(name)]}"
        return False, "no license found; check the package and add 'name: reason' to tools/license-allowlist.txt"
    return True, ""


def load_allowlist(path: Path) -> dict[str, str]:
    out = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and ":" in line:
                name, reason = line.split(":", 1)
                out[normalize(name)] = reason.strip()
    return out


def _requires(name: str) -> list[str] | None:
    try:
        return metadata.distribution(name).requires or []
    except metadata.PackageNotFoundError:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--output", default=str(ROOT / "THIRD_PARTY_LICENSES.md"))
    ap.add_argument("--requirements", help="space-separated names (default: settings.ini requirements)")
    ap.add_argument("--allowlist", default=str(ROOT / "tools" / "license-allowlist.txt"))
    args = ap.parse_args(argv)
    if args.requirements:
        roots = requirement_names(args.requirements)
    else:
        cfg = configparser.ConfigParser(delimiters=["="])
        cfg.read(ROOT / "settings.ini")
        roots = requirement_names(cfg["DEFAULT"].get("requirements", ""))
    allowlist = load_allowlist(Path(args.allowlist))
    missing = [r for r in roots if _requires(r) is None]
    rows, failed = [], []
    for name in closure(roots, _requires):
        dist = metadata.distribution(name)
        lic = license_of(dist.metadata)
        ok, why = classify(dist.metadata["Name"], lic, allowlist)
        rows.append((dist.metadata["Name"], dist.version, lic or "(none)", why))
        if not ok:
            failed.append(f"{dist.metadata['Name']} {dist.version}: {why}")
    lines = ["# Third-party licenses", "",
             "Runtime dependency closure of villaProductSdk (settings.ini requirements), from `tools/check_licenses.py`",
             f"on Python {sys.version_info.major}.{sys.version_info.minor}. Regenerate after changing requirements.", "",
             "| Package | Version | License | Note |", "|---|---|---|---|"]
    lines += [f"| {n} | {v} | {l.replace('|', '/')} | {w} |" for n, v, l, w in rows]
    if missing:
        lines += ["", f"Not installed when generated (not checked): {', '.join(missing)}"]
    Path(args.output).write_text("\n".join(lines) + "\n")
    print(f"{len(rows)} packages written to {args.output}")
    for f in failed:
        print(f"LICENSE {f}")
    if missing:
        print(f"note: not installed, not checked: {', '.join(missing)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
