# villa-product-sdk

## Build & Test

Merge gate (refinery and polecats run this before merging to `dev`):

```bash
tools/gate.sh            # or: make gate
```

It builds a fresh Python 3.12 venv from the exact pins in `requirements-dev.txt` and runs
`pytest -q tests` in it. Do not run the suite with the host `python3`: it lacks the SDK's
dependencies (`s3bz`, `boto3`, ...) and `tests/test_import.py` fails with
`ModuleNotFoundError` (vps-a8a). Exit 2 means the venv could not be built and nothing was
tested. The tests are offline; never point them at AWS.

Extra pytest arguments pass through, e.g. `tools/gate.sh -q tests/test_import.py`.
