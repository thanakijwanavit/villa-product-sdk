"""Check that a wheel ships only the listed packages (bead vps-0ax).

Usage: python3 tools/check_wheel.py dist/X.whl PACKAGE [PACKAGE ...]

Every file in the wheel must sit under one of the listed packages or in the wheel's own
*.dist-info directory, and every listed package must have an __init__.py. Exits 0 when
that holds, else prints the offending paths and exits 1.
"""
import sys
import zipfile


def problems(names, packages):
    allowed = set(packages)
    out = []
    for name in names:
        top = name.split("/", 1)[0]
        if top.endswith(".dist-info") or top in allowed:
            continue
        out.append(f"not a listed package: {name}")
    for pkg in packages:
        if f"{pkg}/__init__.py" not in names:
            out.append(f"listed package missing: {pkg}/__init__.py")
    return out


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    with zipfile.ZipFile(argv[0]) as zf:
        names = zf.namelist()
    found = problems(names, argv[1:])
    for p in found:
        print(p)
    tops = sorted({n.split("/", 1)[0] for n in names})
    print(f"{argv[0]}: {len(names)} files; top level: {', '.join(tops)}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
