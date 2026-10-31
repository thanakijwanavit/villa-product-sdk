"""Field-by-field comparison of the records two SDK modes return for the same product codes (vps-hqj)."""
from typing import Any, Iterable, List, Mapping

_MISSING = object()


def code_key(code: Any) -> str:
    """A product code as the 7-digit string callers use: version 20 turns keys into ints (171670 -> '0171670')."""
    text = str(code).strip()
    return text.zfill(7) if text.isdigit() else text


def by_code(records: Any, key: str = "iprcode") -> dict:
    """Index a queryList-style answer by product code: a list of records, or a mapping of code -> record.

    Only the index is normalised; the records themselves are compared as returned, so an int-vs-string iprcode
    field still shows up as a difference."""
    if records is None:
        return {}
    if isinstance(records, Mapping):
        if key in records:  # a single record
            return {code_key(records[key]): records}
        return {code_key(code): record for code, record in records.items()}
    return {code_key(record.get(key)): record for record in records}


def _walk(path: str, left: Any, right: Any, out: List[str]) -> None:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        for field in sorted(set(left) | set(right), key=str):
            _walk(f"{path}.{field}", left.get(field, _MISSING), right.get(field, _MISSING), out)
    elif left is _MISSING:
        out.append(f"{path}: only in https = {right!r}")
    elif right is _MISSING:
        out.append(f"{path}: only in lambda = {left!r}")
    elif left != right or type(left) is not type(right):
        out.append(f"{path}: lambda {left!r} != https {right!r}")


def diff_records(lambda_records: Any, https_records: Any, codes: Iterable[str]) -> List[str]:
    """Every difference between the two answers for the given codes, one line each; empty when they agree."""
    left, right = by_code(lambda_records), by_code(https_records)
    out: List[str] = []
    for code in codes:
        a, b = left.get(code_key(code), _MISSING), right.get(code_key(code), _MISSING)
        if a is _MISSING and b is _MISSING:
            out.append(f"{code}: missing from both modes")
        else:
            _walk(str(code), a, b, out)
    return out
