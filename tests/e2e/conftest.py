"""Live e2e and parity suite against dev stages only (vps-hqj).

Run (dev only):
    VILLA_PRODUCT_SDK_E2E=1 VILLA_PRODUCT_API_URL=https://<id>.execute-api.ap-southeast-1.amazonaws.com/dev \\
    VILLA_PRODUCT_API_KEY=... python -m pytest tests/e2e -m live
Offline (the default; every live test is skipped):
    python -m pytest -m "not live"

Lambda mode uses VILLA_PRODUCT_SDK_E2E_BRANCH (default dev-manual) and the caller's AWS credentials. The branch and the
endpoint are checked by guard.py before the first call; the API key is read from the environment and never printed.
"""
import inspect
import os

import pytest

from .guard import check_branch, check_endpoint


def live_enabled(environ=os.environ) -> bool:
    return environ.get("VILLA_PRODUCT_SDK_E2E") == "1"


def pytest_configure(config):
    config.addinivalue_line("markers", "live: calls a deployed dev stack; skipped unless VILLA_PRODUCT_SDK_E2E=1")


def pytest_collection_modifyitems(config, items):
    if live_enabled():
        return
    skip = pytest.mark.skip(reason="live e2e: set VILLA_PRODUCT_SDK_E2E=1 to run against the dev stage")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def dev_branch():
    return check_branch(os.environ.get("VILLA_PRODUCT_SDK_E2E_BRANCH", "dev-manual"))


@pytest.fixture(scope="session")
def lambda_sdk(dev_branch):
    # imported here so the offline suite never needs the SDK's AWS dependencies
    from villaProductSdk.products import ProductSdk

    return ProductSdk(branch=dev_branch)


@pytest.fixture(scope="session")
def https_sdk():
    from villaProductSdk.products import ProductSdk

    if "endpoint" not in inspect.signature(ProductSdk.__init__).parameters:
        pytest.skip("HTTPS mode is not built yet: ProductSdk(endpoint=..., api_key=...) (vps-8hj)")
    url = os.environ.get("VILLA_PRODUCT_API_URL")
    key = os.environ.get("VILLA_PRODUCT_API_KEY")
    if not url or not key:
        pytest.fail("set VILLA_PRODUCT_API_URL (the dev stage) and VILLA_PRODUCT_API_KEY")
    return ProductSdk(endpoint=check_endpoint(url), api_key=key)


@pytest.fixture(params=["lambda", "https"])
def sdk(request):
    return request.getfixturevalue(f"{request.param}_sdk")
