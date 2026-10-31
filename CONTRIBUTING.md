# How to contribute

## How to get started

Before anything else, please install the git hooks that run automatic scripts during each commit and merge to strip the notebooks of superfluous metadata (and avoid merge conflicts). After cloning the repository, run the following command inside it:
```
nbdev_install_git_hooks
```

Before making the repository public or pushing a release, run `tools/secret_scan.sh .`: gitleaks over every commit on every ref and over the files on disk (values redacted); accept a finding only with a `.gitleaks.toml` allowlist entry that says why.

## Running the notebooks in Docker

`docker-compose.yml` serves Jupyter on <http://127.0.0.1:8080> and the docs preview on <http://127.0.0.1:4000>, on
this machine only. Jupyter runs code as root inside the container, so it needs a token: set `JUPYTER_TOKEN` to a long
random value before starting it (compose refuses to start the notebook without one), and open
`http://127.0.0.1:8080/?token=<your token>`.

```
export JUPYTER_TOKEN="$(openssl rand -hex 32)"
docker compose up notebook
```

Keep the token out of the repository (no `.env` file committed). To reach Jupyter from another machine, use an SSH
tunnel (`ssh -L 8080:127.0.0.1:8080 <host>`) rather than publishing the port.

## Before a release

Run `make release-env` once (Python 3.12 tools in `.release-venv`; needs `uv` and `gitleaks`), then `make release-check`. It stops at the first failing gate: clean notebooks, library matches notebooks, offline tests, wheel build, wheel contents, `twine check`, install and import in a fresh Python 3.12 venv, `pip-audit`, and a `gitleaks` scan of the tracked files. `make release` runs it, then uploads those exact files to TestPyPI; the PyPI upload is the separate, manual `make pypi`. Both uploads ask you to type the version at a terminal. Steps: [docs/RELEASE.md](docs/RELEASE.md).

GitHub Actions is not used for this repo: run the checks locally.

## Did you find a bug?

* Ensure the bug was not already reported by searching on GitHub under Issues.
* If you're unable to find an open issue addressing the problem, open a new one. Be sure to include a title and clear description, as much relevant information as possible, and a code sample or an executable test case demonstrating the expected behavior that is not occurring.
* Be sure to add the complete error messages.

#### Did you write a patch that fixes a bug?

* Open a new GitHub pull request with the patch.
* Ensure that your PR includes a test that fails without your patch, and pass with it.
* Ensure the PR description clearly describes the problem and solution. Include the relevant issue number if applicable.

## PR submission guidelines

* Keep each PR focused. While it's more convenient, do not combine several unrelated fixes together. Create as many branches as needing to keep each PR focused.
* Do not mix style changes/fixes with "functional" changes. It's very difficult to review such PRs and it most likely get rejected.
* Do not add/remove vertical whitespace. Preserve the original style of the file you edit as much as you can.
* Do not turn an already submitted PR into your development playground. If after you submitted PR, you discovered that more work is needed - close the PR, do the required work and then submit a new PR. Otherwise each of your commits requires attention from maintainers of the project.
* If, however, you submitted a PR and received a request for changes, you should proceed with commits inside that PR, so that the maintainer can see the incremental fixes and won't need to review the whole PR again. In the exception case where you realize it'll take many many commits to complete the requests, then it's probably best to close the PR, do the work and then submit it again. Use common sense where you'd choose one way over another.

## Do you want to contribute to the documentation?

* Docs are automatically created from the notebooks in the nbs folder.

