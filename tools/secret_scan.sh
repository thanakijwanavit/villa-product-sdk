#!/usr/bin/env bash
# Secret scan of a whole repository before it goes public (vps-v9s): every commit on every ref (a key deleted in a
# later commit is still public once the history is), then the files on disk. Values are redacted; nothing secret is
# printed. A finding is accepted only by a .gitleaks.toml allowlist entry with a reason.
#   tools/secret_scan.sh [repo-path]        exit 0 = no leaks, non-zero = findings or gitleaks missing
set -euo pipefail
repo="${1:-.}"
command -v gitleaks >/dev/null || { echo "secret_scan: gitleaks is not installed" >&2; exit 2; }
config=()
[ -f "$repo/.gitleaks.toml" ] && config=(--config "$repo/.gitleaks.toml")
echo "== gitleaks git: every commit on every ref"
gitleaks git --log-opts=--all --redact --no-banner --exit-code 1 "${config[@]}" "$repo"
echo "== gitleaks dir: files on disk"
gitleaks dir --redact --no-banner --exit-code 1 "${config[@]}" "$repo"
echo "secret_scan: no leaks in history or on disk"
