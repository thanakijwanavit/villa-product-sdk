"""vps-160: ProductSdk / FunctionNames refuse a branch or region that would build invalid AWS names, before any client."""
import importlib
import sys
import types

import pytest

MODULES = ["villaProductSdk.products", "villaProductSdk.inventory", "villaInventorySdk.inventory"]


@pytest.fixture
def mods(monkeypatch):
    s3bz = types.ModuleType("s3bz")
    inner = types.ModuleType("s3bz.s3bz")
    inner.S3 = type("S3", (), {})
    inner.Requests = type("Requests", (), {})
    s3bz.s3bz = inner
    monkeypatch.setitem(sys.modules, "s3bz", s3bz)
    monkeypatch.setitem(sys.modules, "s3bz.s3bz", inner)
    loaded = {name: importlib.import_module(name) for name in MODULES}
    calls = []
    for mod in loaded.values():  # no real Lambda client: count constructions instead
        monkeypatch.setattr(mod, "Lambda", lambda *a, **k: calls.append((a, k)) or object())
    return types.SimpleNamespace(loaded=loaded, calls=calls)


@pytest.mark.parametrize("branch", ["", "Dev", "dev_manual", "-dev", "a" * 43, "dev manual", None])
def test_rejects_bad_branch(mods, branch):
    for mod in mods.loaded.values():
        with pytest.raises(ValueError, match="branch"):
            mod.ProductSdk(branch=branch)
        with pytest.raises(ValueError, match="branch"):
            mod.FunctionNames(branchName=branch)


@pytest.mark.parametrize("region", ["", "AP-SOUTHEAST-1", "ap-southeast", "apsoutheast1", "ap_southeast_1", None])
def test_rejects_bad_region(mods, region):
    for mod in mods.loaded.values():
        with pytest.raises(ValueError, match="region"):
            mod.ProductSdk(branch="dev-manual", region=region)


def test_accepts_dev_manual(mods):
    for mod in mods.loaded.values():
        sdk = mod.ProductSdk()  # defaults: dev-manual, ap-southeast-1
        assert sdk.branchName == "dev-manual" and sdk.region == "ap-southeast-1"
        assert mod.FunctionNames().inputBucket() == "input-product-bucket-dev-manual"
        mod.ProductSdk(branch="master", region="us-east-1")
        mod.ProductSdk(branch="a" * 42)  # longest allowed: input-product-bucket- + 42 = 63
        assert len(mod.FunctionNames(branchName="a" * 42).inputBucket()) == 63


def test_no_client_built_on_invalid_config(mods):
    for mod in mods.loaded.values():
        with pytest.raises(ValueError):
            mod.ProductSdk(branch="Bad_Branch")
        with pytest.raises(ValueError):
            mod.ProductSdk(region="mars-1")
    assert mods.calls == []
    mods.loaded[MODULES[0]].ProductSdk()
    assert len(mods.calls) == 1
