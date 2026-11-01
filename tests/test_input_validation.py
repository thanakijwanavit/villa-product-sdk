"""vps-28b: querySingleProduct, queryList and updateWithS3 refuse a bad input before any S3 save or Lambda
invoke: TypeError for a wrong type, ValueError for a bad value. s3bz is stubbed and the Lambda client and S3.save
are recording fakes, so no AWS call is made."""
import importlib
import json
import sys
import types

import pytest


class Recorder:
    def __init__(self):
        self.invokes, self.saves = [], []

    def invoke(self, functionName, input, invocationType="RequestResponse"):
        self.invokes.append({"functionName": functionName, "input": input, "invocationType": invocationType})
        if invocationType == "Event":
            return True
        return {"statusCode": 200, "body": json.dumps({"ok": True}), "headers": {}}


@pytest.fixture
def sdk(monkeypatch):
    rec = Recorder()

    class S3:
        @staticmethod
        def save(key, objectToSave, bucket="", **kwargs):
            rec.saves.append({"key": key, "bucket": bucket})

    stub = types.ModuleType("s3bz.s3bz")
    stub.S3, stub.Requests = S3, type("Requests", (), {})
    monkeypatch.setitem(sys.modules, "s3bz", types.ModuleType("s3bz"))
    monkeypatch.setitem(sys.modules, "s3bz.s3bz", stub)
    monkeypatch.delitem(sys.modules, "villaProductSdk.products", raising=False)
    products = importlib.import_module("villaProductSdk.products")
    s = products.ProductSdk(branch="dev-manual")
    s.lambdaClient = rec
    s.rec = rec
    yield s
    sys.modules.pop("villaProductSdk.products", None)


ROW = {"iprcode": "0171670", "cprcode": "0171670", "pr_abb": "KALE"}

BAD = [
    # (method, args, error)
    ("querySingleProduct", (None,), TypeError),
    ("querySingleProduct", ("",), ValueError),
    ("querySingleProduct", ("01716a0",), ValueError),
    ("querySingleProduct", (" 0171670",), ValueError),
    ("querySingleProduct", ("٠١٢",), ValueError),  # Arabic-Indic digits pass str.isdigit, not 0-9
    ("querySingleProduct", (True,), TypeError),
    ("querySingleProduct", (-1,), ValueError),
    ("querySingleProduct", (1.5,), TypeError),
    ("queryList", ("0171670",), TypeError),  # a str is not a list of codes
    ("queryList", ([],), ValueError),
    ("queryList", (["0171670", ""],), ValueError),
    ("queryList", (["0171670", None],), TypeError),
    ("queryList", ({"0171670"},), TypeError),
    ("updateWithS3", ([],), ValueError),
    ("updateWithS3", ("x",), TypeError),
    ("updateWithS3", ((ROW,),), TypeError),
    ("updateWithS3", ([ROW, "not a dict"],), TypeError),
    ("updateWithS3", ([{"cprcode": "1"}],), ValueError),
    ("updateWithS3", ([{"iprcode": ""}],), ValueError),
    ("updateWithS3", ([{"iprcode": False}],), TypeError),
]


@pytest.mark.parametrize("method,args,error", BAD, ids=[f"{m}-{i}" for i, (m, _, _) in enumerate(BAD)])
def test_bad_inputs_raise_without_calls(sdk, method, args, error):
    with pytest.raises(error):
        getattr(sdk, method)(*args)
    assert sdk.rec.invokes == [] and sdk.rec.saves == []


def test_valid_inputs_still_invoke(sdk):
    assert sdk.querySingleProduct() == {"ok": True}  # the default iprcode
    assert sdk.querySingleProduct("0171670") == {"ok": True}
    assert sdk.querySingleProduct(171670) == {"ok": True}  # an int, as INTCOLS rows carry
    sdk.queryList(["0217153", 203915, "0000009"])
    sdk.queryList(("0217153",))
    sdk.updateWithS3([ROW, {"iprcode": 171670, "pr_abb": "X"}])
    names = [c["functionName"] for c in sdk.rec.invokes]
    assert names == ["product-get-dev-manual"] * 3 + ["product-get-list-dev-manual"] * 2 + ["product-update-s3-dev-manual"]
    assert len(sdk.rec.saves) == 1 and sdk.rec.saves[0]["bucket"] == "input-product-bucket-dev-manual"
