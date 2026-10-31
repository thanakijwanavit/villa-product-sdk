#!/usr/bin/env bash
# Build-check villaProductSdk, and upload it only when a person asks at a terminal (vps-2tx, vps-0ax).
#
#   scripts/release.sh --dry-run    build into a temp dir, twine check; uploads nothing
#   scripts/release.sh --testpypi   upload dist/ to TestPyPI after you type the version
#   scripts/release.sh --publish    upload dist/ to PyPI after you type the version
#
# --testpypi and --publish build nothing: they upload exactly the dist/ files that `make release-check`
# (tools/release_check.sh) passed, and only while those files and the commit are unchanged since.
# --publish also needs those same files to have gone to TestPyPI first (dist/.testpypi-ok).
# Anything else (no flag, two flags, an upload without a terminal or with a dirty checkout, a missing
# or stale release-check stamp, a wrong answer) exits non-zero before uploading. Needs uv (uvx runs
# twine). See docs/RELEASE.md.
set -euo pipefail

usage() {
  echo "usage: scripts/release.sh --dry-run | --testpypi | --publish" >&2
  exit 2
}

mode=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) [[ -z "$mode" ]] || usage; mode=dry-run ;;
    --testpypi) [[ -z "$mode" ]] || usage; mode=testpypi ;;
    --publish) [[ -z "$mode" ]] || usage; mode=publish ;;
    *) usage ;;
  esac
done
[[ -n "$mode" ]] || usage

cd "$(dirname "$0")/.."
version=$(sed -n 's/^version[[:space:]]*=[[:space:]]*//p' settings.ini)
[[ -n "$version" ]] || { echo "release: no version in settings.ini" >&2; exit 1; }

if [[ "$mode" == dry-run ]]; then
  out=$(mktemp -d)
  trap 'rm -rf "$out"' EXIT
  echo "release: building villaProductSdk $version into $out"
  uv build --out-dir "$out"
  echo "release: checking the distributions"
  uvx twine check --strict "$out"/*
  echo "release: dry run: build and check passed. To upload: make release-check, then"
  echo "  scripts/release.sh --testpypi, then scripts/release.sh --publish"
  echo "release: nothing was uploaded"
  exit 0
fi

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "release: commit your changes first: PyPI gets what is committed; nothing was uploaded" >&2
  exit 3
fi

# Only the files release-check passed, at this commit, unchanged since.
stale() { echo "release: $1; run make release-check again; nothing was uploaded" >&2; exit 5; }
[[ -f dist/.release-check-ok && -f dist/.release-check-head ]] || stale "dist/ has no release-check stamp"
[[ "$(cat dist/.release-check-head)" == "$(git rev-parse HEAD)" ]] || stale "release-check ran at another commit"
(cd dist && sha256sum --quiet --strict -c .release-check-ok) || stale "dist/ changed since release-check"
mapfile -t files < <(sed 's/^[0-9a-f]*  //; s|^|dist/|' dist/.release-check-ok)
for f in "${files[@]}"; do
  [[ "$(basename "$f")" == [Vv]illa[Pp]roduct[Ss]dk-"$version"[-.]* ]] || stale "$f is not version $version"
done

if [[ "$mode" == publish ]] && ! cmp -s dist/.release-check-ok dist/.testpypi-ok; then
  echo "release: upload these files to TestPyPI first (scripts/release.sh --testpypi); nothing was uploaded" >&2
  exit 5
fi

# Last guard before the prompt: an upload is only ever a person at a terminal, never a script or an agent.
if [[ ! -t 0 ]]; then
  echo "release: --$mode needs an interactive terminal to confirm; nothing was uploaded" >&2
  exit 3
fi

repo=pypi
[[ "$mode" == testpypi ]] && repo=testpypi
read -r -p "Upload villaProductSdk $version to $repo? A version cannot be replaced once uploaded. Type $version to confirm: " answer
if [[ "$answer" != "$version" ]]; then
  echo "release: not confirmed; nothing was uploaded" >&2
  exit 4
fi
uvx twine upload --repository "$repo" "${files[@]}"
if [[ "$mode" == testpypi ]]; then
  cp dist/.release-check-ok dist/.testpypi-ok
  echo "release: uploaded villaProductSdk $version to TestPyPI; check it, then: scripts/release.sh --publish"
else
  echo "release: uploaded villaProductSdk $version; tag it: git tag v$version && git push origin v$version"
fi
