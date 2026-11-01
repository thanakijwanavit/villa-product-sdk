"""vps-xh2: updateWithS3 never casts a barcode to int. pr_barcode and pr_barcode2 (BARCODECOLS) go to S3 as strings
of digits, unchanged, so a GTIN with a leading zero (a UPC-A written as a 13-digit EAN) survives. A barcode that is
not a str of digits or a non-negative int is refused before anything is saved or invoked. Offline: lambdasdk and s3bz
are the recording fakes from conftest.py."""
import copy

import pytest

UPC_AS_EAN = "0012345678905"  # GS1 prefix 001: a US or Canada UPC-A written as a 13-digit EAN


@pytest.fixture
def products(load_sdk):
    return load_sdk("villaProductSdk.products")


def upload(products, fake_aws, rows):
    """The rows updateWithS3 saved to S3 for one call."""
    products.ProductSdk(branch="dev-manual").updateWithS3(rows, inputKeyName="k-xh2")
    [save] = fake_aws.saves
    return save["objectToSave"]


def test_barcode_columns_are_not_int_columns(products):
    assert products.BARCODECOLS == ["pr_barcode", "pr_barcode2"]
    assert set(products.BARCODECOLS).isdisjoint(products.INTCOLS)
    assert set(products.INTCOLS) == {"iprcode", "cprcode", "oprcode", "sellingPrice"}
    assert "BARCODECOLS" in products.__all__


def test_a_leading_zero_survives_the_upload(products, fake_aws):
    [row] = upload(products, fake_aws, [{"iprcode": "0171670", "cprcode": "0171670", "pr_barcode": UPC_AS_EAN,
                                         "pr_barcode2": "8850999320014"}])
    assert row["pr_barcode"] == UPC_AS_EAN and row["pr_barcode2"] == "8850999320014"
    assert row["iprcode"] == 171670 and row["cprcode"] == 171670  # the code columns are still cast


def test_an_int_barcode_is_sent_as_its_digits(products, fake_aws):
    [row] = upload(products, fake_aws, [{"iprcode": "0171670", "pr_barcode": 8850999320014}])
    assert row["pr_barcode"] == "8850999320014"


def test_a_row_without_barcodes_is_unchanged(products, fake_aws):
    [row] = upload(products, fake_aws, [{"iprcode": "0171670", "pr_abb": "KALE"}])
    assert row == {"iprcode": 171670, "pr_abb": "KALE"}


@pytest.mark.parametrize("column, value, error", [
    ("pr_barcode", None, TypeError),
    ("pr_barcode", 8850999320014.0, TypeError),  # a float column (pandas with NaN) has already lost any leading zero
    ("pr_barcode", True, TypeError),
    ("pr_barcode2", "", ValueError),
    ("pr_barcode", "none", ValueError),  # the old catalogue export's placeholder for no barcode
    ("pr_barcode", "abc", ValueError),
    ("pr_barcode", " 0012345678905", ValueError),
    ("pr_barcode2", -5, ValueError),
])
def test_a_bad_barcode_is_refused_before_anything_is_saved(products, fake_aws, column, value, error):
    rows = [{"iprcode": "0171670", "pr_barcode": UPC_AS_EAN}, {"iprcode": "0217153", column: value}]
    with pytest.raises(error, match=rf"data\[1\]\.{column}\b"):
        products.ProductSdk(branch="dev-manual").updateWithS3(rows)
    assert fake_aws.saves == [] and fake_aws.invocations == []


def test_the_caller_rows_are_not_changed(products, fake_aws):
    rows = [{"iprcode": "0171670", "pr_barcode": UPC_AS_EAN, "pr_barcode2": 8850999320014}]
    before = copy.deepcopy(rows)
    upload(products, fake_aws, rows)
    assert rows == before
