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

test:
	nbdev_test_nbs

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