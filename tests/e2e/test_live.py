"""Every public ProductSdk method against the dev stage, in both modes, and Lambda-vs-HTTPS parity (vps-hqj).

Skipped unless VILLA_PRODUCT_SDK_E2E=1 (see conftest.py). Writes only 9999xxx test records and removes them.
"""
import pytest

from .guard import PARITY_CODES, make_test_code, write_guard
from .parity import by_code, code_key, diff_records

pytestmark = pytest.mark.live
SAMPLE = PARITY_CODES[0]


def test_query_single_product(sdk):
    record = sdk.querySingleProduct(SAMPLE)
    assert record, f"no record for {SAMPLE}"
    assert SAMPLE in by_code(record)


def test_query_list(sdk):
    found = by_code(sdk.queryList(list(PARITY_CODES)))
    assert sorted(found) == sorted(PARITY_CODES)


def test_all_query(sdk):
    everything = sdk.allQuery()
    assert everything, "allQuery returned nothing"
    assert SAMPLE in by_code(everything)


def test_upload_ingest_then_sync(sdk):
    # Criterion 2: the suite must remove what it writes. Without a delete call it would leave records behind on dev,
    # so the write is not made at all until the SDK offers one.
    delete = getattr(sdk, "deleteProducts", None)
    if delete is None:
        pytest.skip("no deleteProducts(iprcodes) in this SDK mode: test records could not be removed")
    records = write_guard(
        [{"iprcode": make_test_code(n), "name": f"vps-hqj e2e {n}"} for n in range(2)]
    )
    codes = [r["iprcode"] for r in records]
    try:
        sdk.updateWithS3(records, inputKeyName=f"e2e-vps-hqj-{codes[0]}")
        stored = by_code(sdk.queryList(codes))
        assert sorted(stored) == sorted(codes)
        assert sdk.syncS3() is not None
    finally:
        delete(codes)
    assert not by_code(sdk.queryList(codes)), "test records were not removed"


def test_parity_lambda_vs_https(lambda_sdk, https_sdk):
    differences = diff_records(
        lambda_sdk.queryList(list(PARITY_CODES)), https_sdk.queryList(list(PARITY_CODES)), PARITY_CODES
    )
    for code in PARITY_CODES:
        differences += diff_records(
            lambda_sdk.querySingleProduct(code), https_sdk.querySingleProduct(code), [code_key(code)]
        )
    assert not differences, "Lambda and HTTPS modes differ:\n" + "\n".join(differences)
