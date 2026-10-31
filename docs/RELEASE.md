---
title: Releasing villaProductSdk
---

# Releasing villaProductSdk to PyPI

There is no CI: this org does not use GitHub Actions, and the old workflow (Python 3.6,
`nbdev_test_nbs` against the real dev Lambdas) was removed in vps-2tx. A release is a person at a
terminal running `scripts/release.sh`. You need [uv](https://docs.astral.sh/uv/); `uvx` runs twine.

## 1. Bump the version

The version lives in `settings.ini` (`version = 0.0.19`); `setup.py` reads it from there. Raise it,
since PyPI never accepts the same version twice. `nbdev_bump_version` raises it in `settings.ini` and
`villaProductSdk/__init__.py` together (they disagree today: 0.0.19 against 0.0.17; vps-3ug unifies
them). Commit the bump.

## 2. Test locally

Run the tests before any release. Today these are the notebook tests (`make test`, i.e.
`nbdev_test_nbs`). They call the **dev** Lambdas, so run them only with dev AWS credentials, never
production ones. Use the offline unit tests instead once they exist (vps-l7s).

## 3. Build and check: the dry run

```bash
scripts/release.sh --dry-run      # or: make release-dry-run
```

This builds the sdist and wheel with `uv build` into a temporary directory, runs
`twine check --strict` on them, and prints the upload command it would run. It uploads nothing and
needs no PyPI credentials. Fix whatever fails before going on.

## 4. Publish

```bash
scripts/release.sh --publish      # or: make release
```

It refuses (non-zero, nothing uploaded) unless it runs in an interactive terminal on a clean
checkout. It builds and checks again, then asks you to type the version. Anything else stops it.
The upload uses twine's usual credentials: `~/.pypirc` or `TWINE_USERNAME=__token__` and
`TWINE_PASSWORD=<a PyPI API token>`. Keep the token out of the shell history and the repository.

Then tag the release: `git tag v<version> && git push origin v<version>`.

Agents never run `--publish`: publishing is a person's decision.
