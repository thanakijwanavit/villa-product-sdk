"""vps-u5v: FunctionNames (branch -> Lambda function and S3 bucket names) and validateConfig have one definition.

They live in names.ipynb, which nbdev exports to villaProductSdk/names.py. villaProductSdk.products,
villaProductSdk.inventory and villaInventorySdk.inventory import them instead of keeping their own copies,
which had drifted (vps-6fo: villaInventorySdk's singleQuery named the S3 update Lambda; only products.py had
listQuery).

Offline: the SDK modules are imported fresh against stub third-party packages (s3bz, lambdasdk, nicHelper,
awsSchema, ...), so no AWS call or credential is needed and the packages need not be installed. sys.modules
and the package attributes are restored afterwards.
"""
import contextlib
import importlib
import json
import pathlib
import re
import sys
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGES = ('villaProductSdk', 'villaInventorySdk')
SDK_MODULES = ('villaProductSdk.products', 'villaProductSdk.inventory', 'villaInventorySdk.inventory')

EXPECTED_DEV_MANUAL = {
    'dumpToS3': 'product-dump-s3-dev-manual',
    'updateProduct': 'product-update-dev-manual',
    'updateS3': 'product-update-s3-dev-manual',
    'singleQuery': 'product-get-dev-manual',
    'allQuery': 'product-get-all-dev-manual',
    'inputBucket': 'input-product-bucket-dev-manual',
    'inventoryBucket': 'product-bucket-dev-manual',
    'listQuery': 'product-get-list-dev-manual',
}

_MISSING = object()


def _stub_modules():
    """Stand-ins for every third-party import of the SDK modules; enough for them to import and define classes."""
    def mod(name, **attrs):
        module = types.ModuleType(name)
        vars(module).update(attrs)
        return module

    def add_method(cls):
        def decorator(func):
            setattr(cls, func.__name__, func)
            return func
        return decorator

    class _AnyAttribute(type):
        def __getattr__(cls, name):  # e.g. Undefined.EXCLUDE, Event.event used in default arguments
            return cls

    class Stub(metaclass=_AnyAttribute):
        def __init__(self, *args, **kwargs):
            pass

    return {
        'botocore': mod('botocore'), 'botocore.config': mod('botocore.config', Config=Stub),
        'boto3': mod('boto3', client=Stub),
        's3bz': mod('s3bz'), 's3bz.s3bz': mod('s3bz.s3bz', S3=Stub, Requests=Stub),
        'lambdasdk': mod('lambdasdk'),
        'lambdasdk.lambdasdk': mod('lambdasdk.lambdasdk', Lambda=Stub, InvocationType=Stub),
        'ujson': json,
        'nicHelper': mod('nicHelper'),
        'nicHelper.wrappers': mod('nicHelper.wrappers', add_method=add_method),
        'nicHelper.exception': mod('nicHelper.exception', errorString=lambda *a, **k: ''),
        'awsSchema': mod('awsSchema'), 'awsSchema.apigateway': mod('awsSchema.apigateway', Event=Stub, Response=Stub),
        'dataclasses_json': mod('dataclasses_json', dataclass_json=lambda cls=None, **k: cls or (lambda c: c),
                                Undefined=Stub),
    }


@contextlib.contextmanager
def _fresh_sdk_modules():
    """Import the three SDK modules (and villaProductSdk.schema) fresh against the stubs, then put sys.modules
    and the `inventory`/`products`/`schema` package attributes back exactly as they were."""
    stubs = _stub_modules()
    reloaded = SDK_MODULES + ('villaProductSdk.schema',)
    packages = {name: importlib.import_module(name) for name in PACKAGES}  # __init__ only sets __version__
    saved_modules = {name: sys.modules.get(name, _MISSING) for name in (*stubs, *reloaded)}
    saved_attrs = {(pkg, attr): vars(packages[pkg]).get(attr, _MISSING)
                   for pkg, attr in (name.rsplit('.', 1) for name in reloaded)}
    try:
        sys.modules.update(stubs)
        for name in reloaded:
            sys.modules.pop(name, None)
        yield {name: importlib.import_module(name) for name in SDK_MODULES}
    finally:
        for name, module in saved_modules.items():
            if module is _MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        for (pkg, attr), value in saved_attrs.items():
            if value is _MISSING:
                vars(packages[pkg]).pop(attr, None)
            else:
                setattr(packages[pkg], attr, value)


@pytest.fixture
def sdk_modules():
    with _fresh_sdk_modules() as modules:
        yield modules


def _name_table(cls, branch):
    names = cls(branch)
    methods = sorted(n for n, v in vars(cls).items() if callable(v) and not n.startswith('_'))
    return {n: getattr(names, n)() for n in methods}


@pytest.mark.parametrize('definition', [r'^class FunctionNames\b', r'^def validateConfig\b'])
def test_exactly_one_definition_in_the_packages(definition):
    defining = sorted(str(p.relative_to(ROOT)) for pkg in PACKAGES for p in (ROOT / pkg).rglob('*.py')
                      if re.search(definition, p.read_text(encoding='utf8'), re.MULTILINE))
    assert defining == ['villaProductSdk/names.py']


def test_every_exported_function_names_is_the_same_class(sdk_modules):
    from villaProductSdk.names import FunctionNames, validateConfig
    for name, module in sdk_modules.items():
        assert module.FunctionNames is FunctionNames, name
        assert module.validateConfig is validateConfig, name
        assert 'FunctionNames' in module.__all__, name
        assert type(module.ProductSdk(branch='x').functionNames) is FunctionNames, name
    assert 'validateConfig' in sdk_modules['villaProductSdk.products'].__all__


def test_name_table_for_dev_manual():
    from villaProductSdk.names import FunctionNames
    assert _name_table(FunctionNames, 'dev-manual') == EXPECTED_DEV_MANUAL
    assert FunctionNames().branchName == 'dev-manual'
    with pytest.raises(ValueError, match='branch'):
        FunctionNames('Not_A_Branch')  # vps-160 validation travels with the class


def test_inventory_sdk_single_query_reads_product_get(sdk_modules):
    names = sdk_modules['villaInventorySdk.inventory'].FunctionNames('x')
    assert names.singleQuery() == 'product-get-x'
    assert names.updateS3() == 'product-update-s3-x'


def test_the_fixture_restores_sys_modules():
    before = {n: sys.modules.get(n, _MISSING) for n in (*SDK_MODULES, 'villaProductSdk.schema', 's3bz', 'ujson')}
    with _fresh_sdk_modules() as modules:
        assert sys.modules['s3bz.s3bz'].S3.__name__ == 'Stub'
        assert all(sys.modules[n] is m for n, m in modules.items())
    after = {n: sys.modules.get(n, _MISSING) for n in before}
    assert all(after[n] is before[n] for n in before)


def _cells(notebook):
    return [(''.join(c['source']), c['cell_type'])
            for c in json.loads((ROOT / notebook).read_text(encoding='utf8'))['cells']]


def _exported_code(notebook):
    """Code of the `#export` cells, without the flag line, as nbdev 1 writes it into the module."""
    out = []
    for source, kind in _cells(notebook):
        lines = source.split('\n')
        if kind == 'code' and re.match(r'^\s*#\s*exports?\s*$', lines[0]):
            out.append('\n'.join(lines[1:]))
    return out


def test_notebook_and_generated_module_stay_in_sync():
    names_py = (ROOT / 'villaProductSdk' / 'names.py').read_text(encoding='utf8')
    assert names_py.startswith('# AUTOGENERATED! DO NOT EDIT! File to edit: names.ipynb')
    assert _cells('names.ipynb')[0][0].strip() == '# default_exp names'
    exported = _exported_code('names.ipynb')
    assert any('def validateConfig' in code for code in exported)
    assert any(code.startswith('class FunctionNames:') for code in exported)
    # nbdev 1 writes each cell as is, minus trailing spaces on each line, after a blank line and '# Cell'.
    module_cells = names_py.split('\n\n# Cell\n')[1:]
    assert module_cells == [re.sub(r' +$', '', code, flags=re.MULTILINE) for code in exported]
    # No other notebook defines them; product-sdk.ipynb imports them in an exported cell.
    for notebook in sorted(p.name for p in ROOT.glob('*.ipynb') if p.name != 'names.ipynb'):
        for source, _ in _cells(notebook):
            assert not re.search(r'^(class FunctionNames|def validateConfig)\b', source, re.MULTILINE), notebook
    assert any('from villaProductSdk.names import validateConfig, FunctionNames' in code
               for code in _exported_code('product-sdk.ipynb'))
    nbdev_index = importlib.import_module('villaProductSdk._nbdev')
    assert nbdev_index.index['FunctionNames'] == nbdev_index.index['validateConfig'] == 'names.ipynb'
    assert 'names.py' in nbdev_index.modules
