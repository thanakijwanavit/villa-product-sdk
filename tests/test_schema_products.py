"""vps-18k: how villaProductSdk.schema parses a products payload (Product, Products, Event.getProducts)."""
import json

import pytest

from villaProductSdk.schema import Event, Product, Products

# two rows of README.md's sampleProducts
ROWS = [
    {"cprcode": "0171670", "iprcode": "0171670", "oprcode": "0171670", "ordertype": "Y", "pr_abb": "JIRAPAT YOUNG KALE 2",
     "pr_active": "Y", "pr_cgcode": "05", "pr_code": "0171670", "pr_dpcode": "19", "pr_engname": "IRAPAT YOUNG KALE 200 G.",
     "pr_ggcode": "057", "pr_market": "JIRAPAT ยอดคะน้า 200 G.", "pr_name": "JIRAPAT ยอดคะน้า 200 G.", "pr_puqty": "1",
     "pr_sa_method": "1", "pr_sucode1": "CM845     ", "pr_suref3": "A", "prtype": "I", "psqty": "1", "pstype": "1"},
    {"cprcode": "0235141", "iprcode": "0235141", "oprcode": "0235141", "ordertype": "Y", "pr_abb": "EEBOO-PZCT3-PUZZLE",
     "pr_active": "Y", "pr_cgcode": "08", "pr_code": "0235141", "pr_dpcode": "19",
     "pr_engname": "EEBOO,ANIMAL COUNTING PUZZLE_3ED,PZCT3", "pr_ggcode": "113", "pr_market": "eeboo,PUZZLE-PZCT3",
     "pr_name": "EEBOO-PZCT3-ตัวต่อนับเลข ANIMAL COUNTING_3ED", "pr_puqty": "1", "pr_sa_method": "1",
     "pr_sucode1": "CM1979    ", "pr_suref3": "A", "prtype": "I", "psqty": "1", "pstype": "1"},
]
KEPT = ("cprcode", "iprcode", "oprcode", "ordertype", "pr_abb")


def test_event_get_products_parses_list():
    products = Event(body=json.dumps({"products": ROWS})).getProducts()
    assert isinstance(products, Products) and len(products.products) == 2
    for parsed, row in zip(products.products, ROWS):
        assert isinstance(parsed, Product)
        assert {k: getattr(parsed, k) for k in KEPT} == {k: row[k] for k in KEPT}


def test_products_json_round_trip():
    p = Products.from_dict({"products": ROWS})
    assert Products.from_json(p.to_json()) == p


def test_product_missing_required_field_raises():
    row = {k: v for k, v in ROWS[0].items() if k != "iprcode"}
    with pytest.raises(KeyError):
        Product.from_dict(row)
    with pytest.raises(KeyError):
        Event(body=json.dumps({"products": [row]})).getProducts()


def test_product_extra_fields_ignored():
    parsed = Product.from_dict(ROWS[0])
    assert set(parsed.to_dict()) == set(KEPT)  # pr_name, pr_engname, pr_active, ... are dropped
    assert not hasattr(parsed, "pr_name")
