"""Offline checks of the e2e suite's own guards and parity diff (vps-hqj): no network, no SDK import."""
import pytest

from .conftest import live_enabled
from .guard import NotDevError, PARITY_CODES, check_branch, check_endpoint, make_test_code, write_guard
from .parity import by_code, diff_records


@pytest.mark.parametrize("branch", ["dev", "dev-manual", "dev-hqj"])
def test_dev_branches_pass(branch):
    assert check_branch(branch) == branch


@pytest.mark.parametrize("branch", ["master", "prod", "production", "main", "dev-prod", "staging", "", "Dev", "devx"])
def test_other_branches_are_refused(branch):
    with pytest.raises(NotDevError):
        check_branch(branch)


@pytest.mark.parametrize(
    "url",
    [
        "https://abc123.execute-api.ap-southeast-1.amazonaws.com/dev",
        "https://abc123.execute-api.ap-southeast-1.amazonaws.com/dev/",
        "https://product.dev.example.com/",
        "https://products-api.execute-api.ap-southeast-1.amazonaws.com/dev",
    ],
)
def test_dev_endpoints_pass(url):
    assert check_endpoint(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "https://abc123.execute-api.ap-southeast-1.amazonaws.com/prod",
        "https://abc123.execute-api.ap-southeast-1.amazonaws.com/v1",
        "https://abc123.execute-api.ap-southeast-1.amazonaws.com/dev-manual-prod",
        "https://abc123.execute-api.ap-southeast-1.amazonaws.com/production/dev",
        "https://product.dev.example.com/prod",
        "https://product.dev.example.com/dev/stage",
        "https://prod.dev.example.com/dev",
        "http://abc123.execute-api.ap-southeast-1.amazonaws.com/dev",
        "https://product.example.com/",
        "",
        None,
    ],
)
def test_other_endpoints_are_refused(url):
    with pytest.raises(NotDevError):
        check_endpoint(url)


def test_writes_only_test_records():
    assert make_test_code(7) == "9999007"
    assert write_guard([{"iprcode": "9999000"}, {"iprcode": "9999001"}])
    with pytest.raises(NotDevError):
        write_guard([{"iprcode": "9999000"}, {"iprcode": "0171670"}])
    with pytest.raises(NotDevError):
        write_guard([])
    with pytest.raises(ValueError):
        make_test_code(1000)


def test_live_runs_only_when_asked():
    assert not live_enabled({})
    assert not live_enabled({"VILLA_PRODUCT_SDK_E2E": "true"})
    assert live_enabled({"VILLA_PRODUCT_SDK_E2E": "1"})


def test_identical_answers_have_no_differences():
    rows = [{"iprcode": "0171670", "name": "A", "price": {"normal": 10}}]
    assert diff_records(rows, {"0171670": dict(rows[0])}, ["0171670"]) == []


def test_every_difference_is_listed_field_by_field():
    lam = [
        {"iprcode": "0171670", "name": "A", "price": {"normal": 10, "member": 9}, "old": 1},
        {"iprcode": "0217153", "name": "B"},
    ]
    https = [
        {"iprcode": 171670, "name": "A", "price": {"normal": 11, "member": 9}, "new": 2},
    ]
    assert diff_records(lam, https, ["0171670", "0217153", "0182223"]) == [
        "0171670.iprcode: lambda '0171670' != https 171670",
        "0171670.new: only in https = 2",
        "0171670.old: only in lambda = 1",
        "0171670.price.normal: lambda 10 != https 11",
        "0217153: only in lambda = {'iprcode': '0217153', 'name': 'B'}",
        "0182223: missing from both modes",
    ]


def test_type_changes_are_differences():
    assert diff_records([{"iprcode": "1", "qty": 1}], [{"iprcode": "1", "qty": 1.0}], ["1"]) == [
        "1.qty: lambda 1 != https 1.0"
    ]


def test_by_code_takes_a_single_record_a_list_or_a_mapping():
    record = {"iprcode": "0171670"}
    assert by_code(record) == by_code([record]) == by_code({"171670": record}) == {"0171670": record}
    assert by_code(None) == {}


def test_parity_codes_are_fixed():
    assert PARITY_CODES == ("0171670", "0217153", "0182223", "0235141", "0124461")
