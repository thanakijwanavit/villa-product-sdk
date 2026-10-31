# Changelog

All notable changes to villaProductSdk. Versions follow the numbers published on PyPI.

## Unreleased

### Documentation
- README rewritten: install, supported Python versions, authentication (Lambda mode), stages, every public method with its inputs, output and errors, a dev-stage example, security notes and known issues.
- Added this changelog.
- CONTRIBUTING.md now matches the repository layout (notebooks at the repository root).

### Notes
- `settings.ini` says 0.0.19 and `villaProductSdk/__init__.py` says 0.0.17, but 0.0.20 is already on PyPI. The next release must be numbered above 0.0.20 (vps-3ug unifies the version).

## 0.0.20 (PyPI, 2021-01-27)

This is the latest release on PyPI. It was built from a state that is not in this repository. Compared with this repository's `villaProductSdk/products.py`:
- `allQuery` invokes `product-get-all-feather-<branch>` and reads a feather file with pandas. pandas is not a declared dependency.
- `syncS3` is not included.

## 0.0.19 and earlier

Not recorded. See the git history.
