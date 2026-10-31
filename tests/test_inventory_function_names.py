"""vps-6fo: villaInventorySdk must invoke the same Lambda names as villaProductSdk.

villaInventorySdk ships in the wheel (setup.py find_packages) but nbdev here builds only villaProductSdk,
so nothing kept the two FunctionNames in step: singleQuery named the S3 *update* function, and a
querySingleProduct call started an ingestion instead of a read. No AWS call is made: s3bz and lambdasdk are
stubbed (with monkeypatch, so the stubs do not leak), and villaProductSdk.products is not imported (it needs
the full dependency set)."""
import importlib
import inspect
import sys
import types

import pytest

# Copied from villaProductSdk/products.py FunctionNames (lines 24-30) for branch 'x'.
PRODUCT_SDK_NAMES = {
    'dumpToS3': 'product-dump-s3-x',
    'updateProduct': 'product-update-x',
    'updateS3': 'product-update-s3-x',
    'singleQuery': 'product-get-x',
    'allQuery': 'product-get-all-x',
    'inputBucket': 'input-product-bucket-x',
    'inventoryBucket': 'product-bucket-x',
}


@pytest.fixture
def inventory(monkeypatch):
    calls = []

    class FakeLambda:
        def __init__(self, **kw):
            pass

        def invoke(self, functionName, input, invocationType='RequestResponse'):
            calls.append((functionName, input))
            return {'ok': True}

    s3bz, s3bz_s3bz = types.ModuleType('s3bz'), types.ModuleType('s3bz.s3bz')
    s3bz_s3bz.S3, s3bz_s3bz.Requests = object, object
    lambdasdk, lambdasdk_lambdasdk = types.ModuleType('lambdasdk'), types.ModuleType('lambdasdk.lambdasdk')
    lambdasdk_lambdasdk.Lambda = FakeLambda
    for name, module in {'s3bz': s3bz, 's3bz.s3bz': s3bz_s3bz,
                         'lambdasdk': lambdasdk, 'lambdasdk.lambdasdk': lambdasdk_lambdasdk}.items():
        monkeypatch.setitem(sys.modules, name, module)
    # a fresh import against the stubs, removed again afterwards
    monkeypatch.delitem(sys.modules, 'villaInventorySdk.inventory', raising=False)
    module = importlib.import_module('villaInventorySdk.inventory')
    monkeypatch.delitem(sys.modules, 'villaInventorySdk.inventory')
    return module, calls


def test_single_query_targets_product_get(inventory):
    module, calls = inventory
    assert module.FunctionNames('x').singleQuery() == 'product-get-x'
    module.ProductSdk(branch='x').querySingleProduct(iprcode='0171670')
    assert calls == [('product-get-x', {'iprcode': '0171670'})]


def test_function_names_match_product_sdk(inventory):
    module, _ = inventory
    names = module.FunctionNames('x')
    methods = sorted(n for n, v in vars(module.FunctionNames).items() if inspect.isfunction(v) and n != '__init__')
    assert methods == sorted(PRODUCT_SDK_NAMES), methods
    assert {n: getattr(names, n)() for n in methods} == PRODUCT_SDK_NAMES
