"""vps-6fo: villaInventorySdk must invoke the same Lambda names as villaProductSdk.

villaInventorySdk ships in the wheel (setup.py find_packages) but nbdev here builds only villaProductSdk,
so nothing kept the two FunctionNames in step: singleQuery named the S3 *update* function, and a
querySingleProduct call started an ingestion instead of a read. No AWS call is made: s3bz and lambdasdk are
stubbed, and sys.modules and the villaInventorySdk.inventory attribute are restored afterwards.
villaProductSdk.products is not imported (it needs the full dependency set)."""
import contextlib
import importlib
import inspect
import sys
import types

import pytest

# The names villaProductSdk.names.FunctionNames gives for branch 'x' (one shared class since vps-u5v).
PRODUCT_SDK_NAMES = {
    'dumpToS3': 'product-dump-s3-x',
    'updateProduct': 'product-update-x',
    'updateS3': 'product-update-s3-x',
    'singleQuery': 'product-get-x',
    'allQuery': 'product-get-all-x',
    'inputBucket': 'input-product-bucket-x',
    'inventoryBucket': 'product-bucket-x',
    'listQuery': 'product-get-list-x',
}


_MISSING = object()
_STUBBED = ('s3bz', 's3bz.s3bz', 'lambdasdk', 'lambdasdk.lambdasdk', 'villaInventorySdk.inventory')


@contextlib.contextmanager
def _inventory_with_stubs():
    """villaInventorySdk.inventory imported fresh against stub s3bz/lambdasdk. Afterwards sys.modules and the
    parent package's `inventory` attribute (which an import sets) are exactly as before, so no later test can
    reach the stubbed module (review cx-1793485140-2382118)."""
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
    package = importlib.import_module('villaInventorySdk')  # __init__ only sets __version__
    saved_modules = {name: sys.modules.get(name, _MISSING) for name in _STUBBED}
    saved_attr = vars(package).get('inventory', _MISSING)
    try:
        sys.modules.update({'s3bz': s3bz, 's3bz.s3bz': s3bz_s3bz,
                            'lambdasdk': lambdasdk, 'lambdasdk.lambdasdk': lambdasdk_lambdasdk})
        sys.modules.pop('villaInventorySdk.inventory', None)
        yield importlib.import_module('villaInventorySdk.inventory'), calls
    finally:
        for name, module in saved_modules.items():
            if module is _MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        if saved_attr is _MISSING:
            vars(package).pop('inventory', None)
        else:
            package.inventory = saved_attr


@pytest.fixture
def inventory():
    with _inventory_with_stubs() as loaded:
        yield loaded


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


def test_the_stubbed_module_does_not_leak():
    """Before and after: the same sys.modules entries and the same package attribute, whether or not the
    real module was imported first."""
    package = importlib.import_module('villaInventorySdk')
    original = (sys.modules.get('villaInventorySdk.inventory', _MISSING), vars(package).get('inventory', _MISSING))
    sys.modules.pop('villaInventorySdk.inventory', None)
    vars(package).pop('inventory', None)
    try:
        _check_no_leak(package)
    finally:
        for target, value in ((sys.modules, original[0]), (vars(package), original[1])):
            key = 'villaInventorySdk.inventory' if target is sys.modules else 'inventory'
            if value is _MISSING:
                target.pop(key, None)
            else:
                target[key] = value


def _check_no_leak(package):
    for preloaded in (False, True):
        if preloaded:  # a real-looking module already imported, as another test might have done
            real = types.ModuleType('villaInventorySdk.inventory')
            sys.modules['villaInventorySdk.inventory'], package.inventory = real, real
        before = ({n: sys.modules.get(n, _MISSING) for n in _STUBBED}, vars(package).get('inventory', _MISSING))
        with _inventory_with_stubs() as (module, _):
            assert package.inventory is module and module.Lambda.__name__ == 'FakeLambda'
        after = ({n: sys.modules.get(n, _MISSING) for n in _STUBBED}, vars(package).get('inventory', _MISSING))
        assert after[0] == before[0] and after[1] is before[1], preloaded
