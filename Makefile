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

test:
	nbdev_test_nbs

# Release (vps-0ax). release-check runs every gate in tools/release_check.sh and stops at the
# first failure; release uploads to TestPyPI only after it passes. The real PyPI upload is
# the separate, manual `make pypi`, which uploads only the dist/ files release-check passed.
release-env:
	uv venv -q -p $(RELEASE_PY) .release-venv
	VIRTUAL_ENV=$(CURDIR)/.release-venv uv pip install -q -r tools/release-requirements.txt

release-check:
	tools/release_check.sh

release: release-check testpypi

testpypi:
	cd dist && sha256sum --quiet -c .release-check-ok
	twine upload --repository testpypi dist/*.whl dist/*.tar.gz

pypi:
	cd dist && sha256sum --quiet -c .release-check-ok
	twine upload --repository pypi dist/*.whl dist/*.tar.gz

conda_release:
	nbdev_conda_package

bump:
	nbdev_bump_version

clean:
	rm -rf dist

.PHONY: all lib sync docs_serve test release-env release-check release testpypi pypi conda_release bump clean
