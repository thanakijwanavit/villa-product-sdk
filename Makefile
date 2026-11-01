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

# merge gate (vps-a8a): pytest in a fresh py3.12 venv with requirements-dev.txt pins
gate:
	tools/gate.sh

release: pypi
	nbdev_conda_package
	nbdev_bump_version

pypi: dist
	twine upload --repository pypi dist/*

dist: clean
	python setup.py sdist bdist_wheel

clean:
	rm -rf dist