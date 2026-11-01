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

release: pypi
	nbdev_conda_package
	nbdev_bump_version

pypi: dist
	twine upload --repository pypi dist/*

dist: clean
	python setup.py sdist bdist_wheel

clean:
	rm -rf dist