.ONESHELL:
SHELL := /bin/bash
SRC = $(wildcard ./*.ipynb)

all: nbdev_template docs

nbdev_template: $(SRC)
	nbdev_build_lib
	touch nbdev_template

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

# Releases go through scripts/release.sh (docs/RELEASE.md): it builds, runs twine check, and uploads
# only with --publish and a typed confirmation. Bump the version in settings.ini first.
release-dry-run:
	./scripts/release.sh --dry-run

release: pypi

pypi:
	./scripts/release.sh --publish

dist: clean
	uv build --out-dir dist

clean:
	rm -rf dist