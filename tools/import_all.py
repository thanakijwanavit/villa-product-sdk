"""Import every module of the given installed packages (bead vps-0ax).

Usage: python tools/import_all.py PACKAGE [PACKAGE ...]

Run it with the interpreter of a fresh venv that has only the wheel installed, from a
directory outside the source tree, so the installed copy is the one imported. Exits 1 and
names each module that fails to import.
"""
import importlib
import pkgutil
import sys
import traceback


def main(packages):
    failed = []
    for pkg in packages:
        try:
            mod = importlib.import_module(pkg)
        except Exception:
            failed.append(pkg)
            traceback.print_exc(limit=3)
            continue
        names = [pkg] + [m.name for m in pkgutil.walk_packages(mod.__path__, pkg + ".")]
        for name in names[1:]:
            try:
                importlib.import_module(name)
            except Exception:
                failed.append(name)
                traceback.print_exc(limit=3)
        print(f"{pkg} from {mod.__file__}: {len(names)} modules")
    if failed:
        print("import failed: " + ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
