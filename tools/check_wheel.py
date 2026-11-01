"""Check that a wheel or sdist ships only the listed packages (bead vps-0ax).

Usage: python3 tools/check_wheel.py dist/X.whl|dist/X.tar.gz PACKAGE [PACKAGE ...]

Wheel: every file must sit under one of the listed packages or in the wheel's own
*.dist-info directory. Sdist: it may also hold tests, docs and metadata, but no Python
package (a top-level directory with an __init__.py) other than the listed ones. In both,
every listed package must have an __init__.py. Exits 0 when that holds, else prints the
offending paths and exits 1.
"""
import sys
import tarfile
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


def sdist_problems(names, packages):
    """names are paths inside the sdist with its leading NAME-VERSION/ directory removed."""
    allowed = set(packages)
    out = []
    for name in names:
        parts = name.split("/")
        if len(parts) == 2 and parts[1] == "__init__.py" and parts[0] not in allowed:
            out.append(f"not a listed package: {name}")
    for pkg in packages:
        if f"{pkg}/__init__.py" not in names:
            out.append(f"listed package missing: {pkg}/__init__.py")
    return out


def read_names(path):
    if path.endswith(".tar.gz"):
        with tarfile.open(path) as tf:
            names = [m.name.split("/", 1)[1] for m in tf.getmembers() if "/" in m.name]
        return names, sdist_problems
    with zipfile.ZipFile(path) as zf:
        return zf.namelist(), problems


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    names, check = read_names(argv[0])
    found = check(names, argv[1:])
    for p in found:
        print(p)
    tops = sorted({n.split("/", 1)[0] for n in names})
    print(f"{argv[0]}: {len(names)} files; top level: {', '.join(tops)}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
