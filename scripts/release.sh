#!/usr/bin/env bash
# Build villaProductSdk, check it, and upload it to PyPI only when asked twice (vps-2tx).
#
#   scripts/release.sh --dry-run   build into a temp dir, twine check, print the upload command; uploads nothing
#   scripts/release.sh --publish   the same, then upload after you type the version at an interactive prompt
#
# Anything else (no flag, both flags, --publish without a terminal, a wrong answer) exits non-zero
# before uploading. Needs uv (uvx runs twine). See docs/RELEASE.md.
set -euo pipefail

usage() {
  echo "usage: scripts/release.sh --dry-run | --publish" >&2
  exit 2
}

mode=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) [[ -z "$mode" ]] || usage; mode=dry-run ;;
    --publish) [[ -z "$mode" ]] || usage; mode=publish ;;
    *) usage ;;
  esac
done
[[ -n "$mode" ]] || usage

cd "$(dirname "$0")/.."
version=$(sed -n 's/^version[[:space:]]*=[[:space:]]*//p' settings.ini)
[[ -n "$version" ]] || { echo "release: no version in settings.ini" >&2; exit 1; }

if [[ "$mode" == publish ]]; then
  # Refuse before building: a publish is only ever a person at a terminal, never a script or an agent.
  if [[ ! -t 0 ]]; then
    echo "release: --publish needs an interactive terminal to confirm; nothing was uploaded" >&2
    exit 3
  fi
  if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    echo "release: commit your changes first: PyPI gets what is committed; nothing was uploaded" >&2
    exit 3
  fi
fi

out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT

echo "release: building villaProductSdk $version into $out"
uv build --out-dir "$out"
echo "release: checking the distributions"
uvx twine check --strict "$out"/*

upload=(uvx twine upload --repository pypi "$out"/*)
if [[ "$mode" == dry-run ]]; then
  echo "release: dry run: build and check passed. --publish would run:"
  printf '  %q' "${upload[@]}"
  echo
  echo "release: nothing was uploaded"
  exit 0
fi

read -r -p "Upload villaProductSdk $version to PyPI? It cannot be replaced once uploaded. Type $version to confirm: " answer
if [[ "$answer" != "$version" ]]; then
  echo "release: not confirmed; nothing was uploaded" >&2
  exit 4
fi
"${upload[@]}"
echo "release: uploaded villaProductSdk $version; tag it: git tag v$version && git push origin v$version"
