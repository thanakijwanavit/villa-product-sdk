"""Offline behaviour tests for villaProductSdk.schema (vps-l7s).

vps-0vc owns tests/test_schema.py (Response.fromDict not mutating its input,
Response.getReturn round trip, Event.key and Event.getBody). This file covers the
public schema methods that vps-0vc leaves out: Event.getProducts, Event.firstKey and
the Product/Products round trip, plus Response.getReturn's output shape. It does not
call Response.fromDict on a dict it reuses, so it passes with and without vps-0vc.
schema.py imports only dataclasses_json and ujson: no AWS, no network.
"""
import json

from villaProductSdk.schema import Event, Product, Products, Response

KALE = {"cprcode": "0171670", "iprcode": "0171670", "oprcode": "0171670",
        "ordertype": "Y", "pr_abb": "JIRAPAT YOUNG KALE 2"}
MILK = {"cprcode": "0000001", "iprcode": "0000002", "oprcode": "0000003",
        "ordertype": "N", "pr_abb": "MILK 1L"}


def test_get_return_is_an_apigateway_proxy_dict():
    out = Response.getReturn(body={"a": 1}, header={"x": "y"}, statusCode=201)
    assert set(out) == {"body", "statusCode", "header"}
    assert isinstance(out["body"], str)
    assert json.loads(out["body"]) == {"a": 1}
    assert out["statusCode"] == 201
    assert out["header"] == {"x": "y"}


def test_get_return_defaults():
    out = Response.getReturn(body=[1, 2])
    assert out["statusCode"] == 200
    assert out["header"] == {}
    assert json.loads(out["body"]) == [1, 2]


def test_event_get_products_parses_body():
    event = Event(body=json.dumps({"products": [KALE, MILK]}))
    products = event.getProducts()
    assert isinstance(products, Products)
    assert products.products == [Product(**KALE), Product(**MILK)]


def test_event_first_key_returns_first_item():
    event = Event(body=json.dumps({"key": "abc", "other": 2}))
    assert event.firstKey() == ("key", "abc")


def test_event_from_dict_ignores_unknown_fields():
    event = Event.from_dict({"body": "{}", "header": {"h": 1}, "unexpected": True})
    assert event == Event(body="{}", header={"h": 1})


def test_products_round_trip():
    products = Products(products=[Product(**KALE), Product(**MILK)])
    assert products.to_dict() == {"products": [KALE, MILK]}
    assert Products.from_json(products.to_json()) == products
    assert Product.from_dict(KALE).to_dict() == KALE
