---
title: Releasing villaProductSdk
---

# Releasing villaProductSdk to PyPI

There is no CI: this org does not use GitHub Actions, and the old workflow (Python 3.6,
`nbdev_test_nbs` against the real dev Lambdas) was removed in vps-2tx. A release is a person at a
terminal: `make release-check`, then `make release` (TestPyPI), then `make pypi`. You need
[uv](https://docs.astral.sh/uv/) (`uvx` runs twine) and [gitleaks](https://github.com/gitleaks/gitleaks).

## 1. Bump the version

The version lives in `settings.ini` (`version = ...`); `setup.py` reads it from there, and
`villaProductSdk/__init__.py` must match it (`tests/test_version.py` checks). Raise both, since PyPI
never accepts the same version twice; `nbdev_bump_version` raises them together. Commit the bump.

## 2. Run the release gate

```bash
make release-env      # once: Python 3.12 tools (nbdev, build, twine, pytest, pip-audit) in .release-venv
make release-check    # tools/release_check.sh
```

`release-check` runs these gates in order and stops at the first failure:

| gate | checks |
|---|---|
| clean-tree | no uncommitted changes to tracked files: the gates check what will be released |
| clean-nbs | `nbdev_clean_nbs` changes no notebook |
| diff-nbs | `nbdev_diff_nbs` is empty: the library matches the notebooks |
| pytest | the offline test suite in `tests/` (no AWS, no network) |
| build | sdist and wheel into `dist/` (emptied first) |
| contents | the wheel holds only the packages in `settings.ini` `packages`, nothing else at top level |
| twine | `twine check --strict dist/*` |
| install | for each version in `settings.ini` `tested_pythons`, a fresh venv installs the wheel and imports every module |
| audit | `pip-audit` of the runtime set that install put in that venv |
| secrets | `gitleaks` on the tracked files at HEAD: zero findings |

On success it writes `dist/.release-check-ok` (the sha256 of each file in `dist/`) and
`dist/.release-check-head` (the commit). Run one gate with `tools/release_check.sh --only <gate>`;
list them with `--list`.

`scripts/release.sh --dry-run` (`make release-dry-run`) is a quicker check: build into a temporary
directory and `twine check`. It uploads nothing and writes no stamp.

## 3. TestPyPI first

```bash
make release          # = make release-check, then scripts/release.sh --testpypi
```

The upload builds nothing: it sends exactly the `dist/` files `release-check` passed. It refuses
(non-zero, nothing uploaded) when the checkout has uncommitted changes, when there is no stamp, when
HEAD moved since `release-check`, when a `dist/` file changed, when a file is not the
`settings.ini` version, or when stdin is not a terminal. Then it asks you to type the version.
Install from TestPyPI and try it:
`pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ villaProductSdk==<version>`.

## 4. Publish to PyPI

```bash
make pypi             # = scripts/release.sh --publish
```

The same checks, and the same files must have gone to TestPyPI first (`dist/.testpypi-ok`). It asks
you to type the version again. The upload uses twine's usual credentials: `~/.pypirc` (sections
`pypi` and `testpypi`) or `TWINE_USERNAME=__token__` and `TWINE_PASSWORD=<an API token>`. Keep the
token out of the shell history and the repository.

Then tag the release: `git tag v<version> && git push origin v<version>`.

Agents never run `--testpypi` or `--publish`: publishing is a person's decision.
