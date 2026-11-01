#!/usr/bin/env bash
# vps-eht planted-key test: a fake AWS key in a local sdist makes tools/scan_pypi_artifacts.sh exit 1 and is reported
# by path, and its value is never printed; the same sdist without the key exits 0. Offline. The key is generated at
# run time and never stored in the repo. Fuller cases: tests/test_scan_pypi_artifacts.py (pytest).
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/src/pkg-0.1/pkg" "$tmp/dist"
echo 'x = 1' >"$tmp/src/pkg-0.1/pkg/__init__.py"

set +e
out=$("$repo/tools/scan_pypi_artifacts.sh" --local "$tmp/dist" --work "$tmp/w" 2>&1)
rc=$?
set -e
[ "$rc" = 2 ] || { echo "FAIL: an empty dist/ must exit 2, got $rc: $out"; exit 1; }

tar -czf "$tmp/dist/pkg-0.1.tar.gz" -C "$tmp/src" pkg-0.1
set +e
out=$("$repo/tools/scan_pypi_artifacts.sh" --local "$tmp/dist" --work "$tmp/w" 2>&1)
rc=$?
set -e
[ "$rc" = 0 ] || { echo "FAIL: the clean sdist must exit 0, got $rc: $out"; exit 1; }

key=$(python3 -c 'import secrets; print("AK" + "IA" + "".join(secrets.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567") for _ in range(16)))')
printf 'AWS_ACCESS_KEY_ID="%s"\n' "$key" >"$tmp/src/pkg-0.1/.env"
tar -czf "$tmp/dist/pkg-0.1.tar.gz" -C "$tmp/src" pkg-0.1
set +e
out=$("$repo/tools/scan_pypi_artifacts.sh" --local "$tmp/dist" --work "$tmp/w" 2>&1)
rc=$?
set -e
shown=${out//$key/<planted key>}
[ "$rc" = 1 ] || { echo "FAIL: the planted key must exit 1, got $rc: $shown"; exit 1; }
grep -qF 'pkg-0.1/.env:1 [aws-access-token]' <<<"$out" || { echo "FAIL: finding not reported by path: $shown"; exit 1; }
if grep -qF "$key" <<<"$out"; then echo "FAIL: the key value was printed"; exit 1; fi
echo "PASS: empty dist/ exits 2, clean sdist exits 0, planted key exits 1 and is reported by path only"
