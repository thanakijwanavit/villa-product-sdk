#!/usr/bin/env bash
# Secret scan of every file of every PyPI release of the given packages (vps-eht); details in scan_pypi_artifacts.py.
#   tools/scan_pypi_artifacts.sh villaProductSdk lambdasdk s3bz nicHelper awsSchema --markdown docs/security/pypi-artifact-scan.md
#   tools/scan_pypi_artifacts.sh --local dist        before `twine upload`
# exit 0 = no findings, 1 = findings (shown as path:line [rule], never the value), 2 = setup error
exec python3 -I "$(dirname "$0")/scan_pypi_artifacts.py" "$@"
