"""Unit tests for villaProductSdk.schema (vps-0vc)."""
import copy

from villaProductSdk.schema import Event, Response


def test_from_dict_does_not_mutate_input():
    raw = {"body": '{"a": 1}', "statusCode": 200, "header": {"x": "y"}}
    before = copy.deepcopy(raw)
    first = Response.fromDict(raw)
    assert raw == before
    second = Response.fromDict(raw)  # used to raise KeyError: 'body'
    assert first == second
    assert first.body == {"a": 1}
    assert first.header == {"x": "y"}


def test_get_return_round_trips():
    body = {"key": "123", "items": [1, 2, 3], "nested": {"k": "v"}}
    returned = Response.getReturn(body=body, header={"h": "1"}, statusCode=201)
    assert isinstance(returned["body"], str)
    parsed = Response.fromDict(returned)
    assert parsed.body == body
    assert parsed.statusCode == 201
    assert parsed.header == {"h": "1"}
    assert "body" in returned


def test_event_key_and_body():
    event = Event.from_dict({"body": '{"key": "abc", "other": 2}', "unknown": "dropped"})
    assert event.key() == "abc"
    assert event.getBody() == {"key": "abc", "other": 2}
    assert event.firstKey() == ("key", "abc")
