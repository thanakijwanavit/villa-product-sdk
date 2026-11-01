"""vps-h5t: docs/API.md and tests/fixtures/https_contract.json are one contract, the HTTPS product API's, in prose and
in machine-readable form. These checks keep the two in step and, once the backend (vps-52s: infra/) or the e2e suite
(vps-hqj: tests/e2e/) is in the tree, check that those stay inside the contract. Offline: no network, no AWS, and the
SDK is not imported."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "tests" / "fixtures" / "https_contract.json").read_text(encoding="utf-8"))
DOC = (ROOT / CONTRACT["doc"]).read_text(encoding="utf-8")
TYPES = {"string", "integer", "array", "object", "string|null"}
ROUTE_ROW = re.compile(r"^\|\s*(GET|POST|PUT|PATCH|DELETE)\s*\|\s*`(/[^`]*)`\s*\|(.*)$", re.MULTILINE)


def section(title: str) -> str:
    """The '## <title>' section of docs/API.md, up to the next '## ' heading."""
    match = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", DOC, re.MULTILINE | re.DOTALL)
    assert match, f"docs/API.md has no '## {title}' section"
    return match.group(1)


def template_routes(text: str) -> set:
    """(method, path) of every `Type: Api` event in a SAM template, flow or block style."""
    routes = set()
    for start in [m.end() for m in re.finditer(r"\bType:\s*Api\b", text)]:
        following = re.search(r"\bType:", text[start:])
        block = text[start:start + following.start()] if following else text[start:]
        path = re.search(r"\bPath:\s*(/[^\s,}]*)", block)
        method = re.search(r"\bMethod:\s*([A-Za-z]+)", block)
        assert path and method, f"an Api event without Path and Method: {block[:160]!r}"
        routes.add((method.group(1).upper(), path.group(1)))
    return routes


def test_routes_are_unique_and_well_formed():
    routes = CONTRACT["routes"]
    assert len({r["name"] for r in routes}) == len(routes)
    assert len({(r["method"], r["path"]) for r in routes}) == len(routes)
    for r in routes:
        assert r["method"] in {"GET", "POST"}, r
        assert r["path"].startswith("/") and not r["path"].endswith("/"), r
        assert r["status"] in {200, 202}, r
        assert isinstance(r["new"], bool) and isinstance(r["retry"], bool), r
        assert r["response"] == "product" or (r["response"] and set(r["response"].values()) <= TYPES), r
        assert r["body"] is None or set(r["body"].values()) <= TYPES, r
        assert set(r["errors"]) <= {400, 404}, r
    # only /ingest is never retried: after a lost answer its upload is already deleted, so a retry answers 404
    assert [r["path"] for r in routes if not r["retry"]] == ["/ingest"]


def test_the_doc_route_table_is_the_fixture():
    documented = ROUTE_ROW.findall(section("Routes"))
    assert [(m, p) for m, p, _ in documented] == [(r["method"], r["path"]) for r in CONTRACT["routes"]]
    for (_, path, rest), route in zip(documented, CONTRACT["routes"]):
        assert ("(new)" in rest) == route["new"], path
        assert f"{route['status']}," in rest, path
        for name in route["sdk"]:
            assert f"`{name}`" in rest, (path, name)


def test_the_doc_limits_table_is_the_fixture():
    rows = re.findall(r"^\|\s*`(\w+)`\s*\|\s*([0-9]+)\s*\|", section("Limits"), re.MULTILINE)
    assert {name: int(value) for name, value in rows} == CONTRACT["limits"]
    assert len(rows) == len(CONTRACT["limits"]), "a limit is listed twice"


@pytest.mark.parametrize("number", [1, 2, 3, 4, 5])
def test_each_question_has_a_recorded_decision(number):
    match = re.search(rf"^### Q{number}\. .+?\n(.*?)(?=^##|\Z)", section("Decisions"), re.MULTILINE | re.DOTALL)
    assert match, f"docs/API.md records no Q{number}"
    assert "**Decision:**" in match.group(1) and "**Why:**" in match.group(1), f"Q{number}"


def test_the_doc_states_what_a_client_decodes_by():
    dump, auth, delete = CONTRACT["dump"], CONTRACT["auth"], CONTRACT["deleteRange"]
    for text in (f'"{dump["format"]}"', dump["objectKey"], dump["contentType"], 'orient="records"',
                 f'{delete["min"]} to {delete["max"]}', auth["header"], auth["envEndpoint"], auth["envApiKey"]):
        assert text in DOC, text


def test_the_delete_range_is_the_e2e_suites_test_codes():
    guard = ROOT / "tests" / "e2e" / "guard.py"
    if not guard.exists():
        pytest.skip("tests/e2e/guard.py (vps-hqj) is not in this tree")
    prefix = re.search(r'^TEST_PREFIX\s*=\s*"([0-9]+)"', guard.read_text(encoding="utf-8"), re.MULTILINE)
    assert prefix, "tests/e2e/guard.py no longer sets TEST_PREFIX to a digit string"
    assert CONTRACT["deleteRange"] == {"min": int(prefix.group(1) + "000"), "max": int(prefix.group(1) + "999")}


def test_the_backend_exposes_no_undocumented_route():
    template = ROOT / "infra" / "template.yaml"
    if not template.exists():
        pytest.skip("infra/template.yaml (vps-52s) is not in this tree")
    exposed = template_routes(template.read_text(encoding="utf-8"))
    assert exposed, "found no Api event in infra/template.yaml"
    assert exposed <= {(r["method"], r["path"]) for r in CONTRACT["routes"]}, sorted(exposed)


def test_the_backend_dump_is_the_documented_format():
    handler = ROOT / "infra" / "handlers" / "product_api.py"
    if not handler.exists():
        pytest.skip("infra/handlers/product_api.py (vps-52s) is not in this tree")
    text = handler.read_text(encoding="utf-8")
    dump = CONTRACT["dump"]
    for literal in (f'"{dump["format"]}"', f'"{dump["objectKey"]}"', f'"{dump["contentType"]}"', "bz2.compress("):
        assert literal in text, literal


def test_template_routes_reads_flow_and_block_style():
    flow = "Events:\n  Api:\n    Type: Api\n    Properties: {RestApiId: !Ref A, Path: /product, Method: GET}\n"
    block = ("Events:\n  Api:\n    Type: Api\n    Properties:\n      RestApiId: !Ref A\n      Method: post\n"
             "      Path: /products/sync\n"
             "  Hourly:\n    Type: Schedule\n    Properties:\n      Schedule: rate(1 hour)\n")
    assert template_routes(flow + block) == {("GET", "/product"), ("POST", "/products/sync")}
