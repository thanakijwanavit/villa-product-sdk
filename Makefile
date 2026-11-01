.ONESHELL:
SHELL := /bin/bash
SRC = $(wildcard ./*.ipynb)
RELEASE_PY ?= 3.12

all: lib docs

lib: $(SRC)
	nbdev_build_lib

sync:
	nbdev_update_lib

docs_serve: docs
	cd docs && bundle exec jekyll serve

docs: $(SRC)
	nbdev_build_docs
	touch docs

# vps-7af: the default test is the offline pytest suite (no AWS, no credentials). The notebooks call live
# Lambda/S3, so running them is its own target; so are the tests marked live.
test:
	python3 -m pytest

test-live:
	python3 -m pytest -m live

test-notebooks-live:
	nbdev_test_nbs

# merge gate (vps-a8a): pytest in a fresh py3.12 venv with requirements-dev.txt pins
gate:
	tools/gate.sh

# Releases (docs/RELEASE.md). release-check runs every gate in tools/release_check.sh, stops at the
# first failure and stamps dist/ (vps-0ax). The uploads go through scripts/release.sh (vps-2tx): each
# asks a person at a terminal to type the version, and uploads only the dist/ files release-check
# passed at the current commit. `make release` = release-check, then TestPyPI. The real PyPI upload
# is the separate, manual `make pypi`, and only after those same files went to TestPyPI.
release-env:
	uv venv -q --clear -p $(RELEASE_PY) .release-venv
	VIRTUAL_ENV=$(CURDIR)/.release-venv uv pip install -q -r tools/release-requirements.txt

release-check:
	tools/release_check.sh

release-dry-run:
	./scripts/release.sh --dry-run

release: release-check testpypi

testpypi:
	./scripts/release.sh --testpypi

pypi:
	./scripts/release.sh --publish

dist: clean
	uv build --out-dir dist

clean:
	rm -rf dist

.PHONY: all lib sync docs_serve test test-live test-notebooks-live gate release-env release-check release-dry-run release testpypi pypi dist clean
