#!/usr/bin/env bash
# Local release gate for villaProductSdk (bead vps-0ax). Run it as `make release-check`.
#
# Usage: tools/release_check.sh            run every gate in order, stop at the first failure
#        tools/release_check.sh --list     print the gate names
#        tools/release_check.sh --only G   run one gate (the gates after "build" need dist/)
#
# Gates, in order:
#   clean-tree   no uncommitted changes to tracked files (the gates check what will be released)
#   clean-nbs    nbdev_clean_nbs changes no notebook
#   diff-nbs     nbdev_diff_nbs is empty: the library matches the notebooks
#   pytest       the offline test suite in tests/
#   build        sdist and wheel into dist/ (dist/ is emptied first)
#   contents     the wheel holds only the packages listed in settings.ini, nothing else at top level
#   twine        twine check dist/*
#   install      for each version in settings.ini tested_pythons: a fresh venv installs the wheel
#                and imports every module of every listed package
#   audit        pip-audit of the runtime set installed by "install" (the first tested Python)
#   secrets      gitleaks on the tracked files at HEAD, zero findings
# On success it writes dist/.release-check-ok with the sha256 of each dist file; `make pypi`
# uploads only when those files are unchanged.
#
# Tools: TOOLS_BIN (default .release-venv/bin, made by `make release-env`) provides nbdev 1.x,
# build, twine, pytest and pip-audit; gitleaks and uv (or pythonX.Y) come from PATH.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
TOOLS_BIN=${TOOLS_BIN:-$ROOT/.release-venv/bin}
GATES=(clean-tree clean-nbs diff-nbs pytest build contents twine install audit secrets)
WORK=$(mktemp -d "${TMPDIR:-/tmp}/release-check.XXXXXX")
trap 'rm -rf "$WORK"' EXIT

tool() {  # tool NAME: path of a tool from TOOLS_BIN, else PATH
  if [ -x "$TOOLS_BIN/$1" ]; then echo "$TOOLS_BIN/$1"; return; fi
  command -v "$1" || { echo "missing tool: $1 (run make release-env)" >&2; return 1; }
}
setting() { python3 -c 'import configparser,sys; c=configparser.ConfigParser(delimiters=["="]); c.read("settings.ini"); print(c["DEFAULT"].get(sys.argv[1], "").strip())' "$1"; }
PACKAGES=$(setting packages)
TESTED_PYTHONS=$(setting tested_pythons)
if [ -z "$PACKAGES" ] || [ -z "$TESTED_PYTHONS" ]; then
  echo "settings.ini needs non-empty packages and tested_pythons" >&2; exit 2
fi
wheel() {
  local w=(dist/*.whl)
  [ ${#w[@]} -eq 1 ] && [ -f "${w[0]}" ] || { echo "expected exactly one wheel in dist/" >&2; return 1; }
  echo "${w[0]}"
}
venv_for() {  # venv_for VERSION DIR
  if command -v uv >/dev/null; then uv venv -q -p "$1" "$2"; else "python$1" -m venv "$2"; fi
}

gate_clean_tree() {
  local dirty; dirty=$(git status --porcelain --untracked-files=no)
  [ -z "$dirty" ] || { echo "uncommitted changes to tracked files:"; echo "$dirty"; return 1; }
}
gate_clean_nbs() {
  "$(tool nbdev_clean_nbs)"
  local dirty; dirty=$(git status --porcelain --untracked-files=no -- '*.ipynb')
  [ -z "$dirty" ] || { echo "nbdev_clean_nbs changed notebooks (run it and commit):"; echo "$dirty"; return 1; }
}
gate_diff_nbs() {
  local out; out=$("$(tool nbdev_diff_nbs)")
  [ -z "$out" ] || { echo "library differs from the notebooks (nbdev_diff_nbs):"; echo "$out" | head -40; return 1; }
}
gate_pytest() { "$(tool pytest)" -q -p no:cacheprovider tests; }
gate_build() {
  rm -rf dist build ./*.egg-info
  "$(tool python)" -m build --no-isolation --sdist --wheel --outdir dist . >"$WORK/build.log" 2>&1 \
    || { tail -30 "$WORK/build.log"; return 1; }
  ls dist
}
gate_contents() { python3 "$ROOT/tools/check_wheel.py" "$(wheel)" $PACKAGES; }
gate_twine() { "$(tool twine)" check --strict dist/*; }
gate_install() {
  local whl; whl=$(wheel)
  for v in $TESTED_PYTHONS; do
    local env="$WORK/py$v"
    venv_for "$v" "$env"
    if command -v uv >/dev/null; then VIRTUAL_ENV="$env" uv pip install -q "$whl"
    else "$env/bin/python" -m pip install -q "$whl"; fi
    (cd "$WORK" && "$env/bin/python" "$ROOT/tools/import_all.py" $PACKAGES)
    echo "python $v: wheel installs and imports"
  done
}
gate_audit() {
  local v=${TESTED_PYTHONS%% *}
  if [ ! -d "$WORK/py$v" ]; then gate_install >/dev/null; fi
  local site; site=$("$WORK/py$v/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
  "$(tool pip-audit)" --progress-spinner off --path "$site"
}
gate_secrets() {
  mkdir -p "$WORK/head"
  git archive HEAD | tar -x -C "$WORK/head"
  "$(tool gitleaks)" dir --no-banner --redact --exit-code 1 "$WORK/head"
}

run_gate() {  # exits the script when the gate fails
  # Run the gate in a subshell, and never call run_gate from an if/&&/|| context: bash
  # ignores set -e inside any command run as a condition, subshells included.
  local g=$1 fn=gate_${1//-/_} rc
  echo "== release-check: $g"
  set +e
  ( set -e; "$fn" )
  rc=$?
  set -e
  if [ "$rc" -ne 0 ]; then echo "release-check FAILED at: $g (exit $rc)"; exit 1; fi
}

case "${1:-}" in
  --list) printf '%s\n' "${GATES[@]}"; exit 0;;
  --only)
    [[ " ${GATES[*]} " == *" ${2:-} "* ]] || { echo "unknown gate: ${2:-}" >&2; exit 2; }
    run_gate "$2"; exit 0;;
  "") ;;
  *) echo "usage: $0 [--list | --only GATE]" >&2; exit 2;;
esac

for g in "${GATES[@]}"; do run_gate "$g"; done
(cd dist && sha256sum -- * > .release-check-ok)
echo "release-check PASSED; dist/.release-check-ok written"
