#!/usr/bin/env bash
# Offline tests for scripts/release.sh's guards (vps-2tx; stamp guards: tests/test_release_check.py, vps-0ax). uv and uvx are replaced by fakes that
# record any call and fail, so nothing is built and nothing can reach PyPI, also if a guard broke.
#   scripts/test_release.sh          (the real dry run: ./scripts/release.sh --dry-run)
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

fakes=$(mktemp -d)
trap 'rm -rf -- "${fakes:?}"' EXIT
for tool in uv uvx; do
  printf '#!/bin/sh\necho "%s $*" >> "%s/called"\nexit 1\n' "$tool" "$fakes" > "$fakes/$tool"
  chmod +x "$fakes/$tool"
done

failed=0
expect() {  # expect "<exit codes>" <description> <args...> (stdin is never a terminal here)
  local want=$1 what=$2; shift 2
  PATH="$fakes:$PATH" ./scripts/release.sh "$@" < /dev/null > /dev/null 2>&1
  local got=$?
  if [[ " $want " == *" $got "* ]]; then echo "ok   $what (exit $got)"; else echo "FAIL $what: exit $got, want $want"; failed=1; fi
}

expect 2 "no flag is a usage error"
expect 2 "an unknown flag is a usage error" --upload
expect 2 "both flags are a usage error" --dry-run --publish
expect 2 "the same flag twice is a usage error" --publish --publish
# Here the checkout is dirty (3) or dist/ has no release-check stamp (5); either way nothing runs.
expect "3 5" "--publish refuses without a stamp or a terminal" --publish
expect "3 5" "--testpypi refuses without a stamp or a terminal" --testpypi
expect 2 "--testpypi with --publish is a usage error" --testpypi --publish

if [[ -e "$fakes/called" ]]; then
  echo "FAIL uv/uvx were called: $(cat "$fakes/called")"; failed=1
else
  echo "ok   uv and uvx were never called"
fi
# shellcheck disable=SC2016  # the literal shell text in release.sh
if grep -q 'read -r -p' scripts/release.sh && grep -q '"$answer" != "$version"' scripts/release.sh; then
  echo "ok   --publish asks for the version before uploading"
else
  echo "FAIL no typed confirmation"; failed=1
fi
exit $failed
