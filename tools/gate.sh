#!/usr/bin/env bash
# Merge gate for this repo (vps-a8a): run the test suite in a fresh Python 3.12 venv holding the exact pins in
# requirements-dev.txt, never the host python3, which lacks the SDK's dependencies (s3bz, boto3, ...).
# Usage: tools/gate.sh [pytest args...]   (default: -q tests)
# Env: GATE_PY (default 3.12, the version requirements-dev.txt is compiled for).
# Needs uv (preferred; fetches Python 3.12 if missing) or a pythonX.Y on PATH. Offline tests only; no AWS.
# Exit: pytest's exit code; 2 when the venv cannot be built.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
py=${GATE_PY:-3.12}
env_dir=$(mktemp -d "${TMPDIR:-/tmp}/vps-gate.XXXXXX")
trap 'rm -rf "$env_dir"' EXIT

build() {
  if command -v uv >/dev/null; then
    uv venv -q -p "$py" "$env_dir/venv" &&
      VIRTUAL_ENV="$env_dir/venv" uv pip install -q -r "$repo/requirements-dev.txt"
  else
    "python$py" -m venv "$env_dir/venv" &&
      "$env_dir/venv/bin/python" -m pip install -q -r "$repo/requirements-dev.txt"
  fi
}
echo "== gate: python $py venv from requirements-dev.txt"
build || { echo "gate: could not build the python $py test venv; nothing was tested" >&2; exit 2; }

[ $# -gt 0 ] || set -- -q tests
echo "== gate: pytest $*"
cd "$repo"
export AWS_EC2_METADATA_DISABLED=true
rc=0
"$env_dir/venv/bin/python" -m pytest -p no:cacheprovider "$@" || rc=$?
exit "$rc"
