"""Dev-only guards for the live e2e and parity suite (vps-hqj).

The suite may only touch dev stages: the Lambda-mode branch name and the HTTPS endpoint are both checked before any
call, and every record the suite writes carries TEST_PREFIX so it can be found and removed. Nothing here imports the
SDK, so these checks run (and are unit-tested) even where the SDK's AWS dependencies are not installed.
"""
import re
from typing import Iterable, Mapping
from urllib.parse import urlparse

# Product codes the old notebooks query against dev-manual (product-sdk.ipynb); the parity run compares these.
PARITY_CODES = ("0171670", "0217153", "0182223", "0235141", "0124461")

# Records the suite writes use 7-digit codes starting 9999 (product keys are converted to int since version 20,
# so a letter prefix could not be ingested); write_guard refuses anything else.
TEST_PREFIX = "9999"

_DEV_BRANCH = re.compile(r"^dev(-[a-z0-9]+)*$")
_NOT_DEV_WORDS = {"prod", "production", "live", "staging", "stage", "stg", "master", "main", "release"}


def _names_non_dev(*parts: str) -> bool:
    """True when any whole word of the parts (split on . - _ /) names a non-dev stage: 'product' is fine, 'prod' is not."""
    return any(word in _NOT_DEV_WORDS for part in parts for word in re.split(r"[^a-z0-9]+", part.lower()))


class NotDevError(RuntimeError):
    """Raised when a branch, endpoint or record is not marked dev / test; the suite stops before any call."""


def check_branch(branch: str) -> str:
    """Accept only dev Lambda branches (dev, dev-manual, dev-<name>); refuse anything else."""
    if not isinstance(branch, str) or not _DEV_BRANCH.match(branch) or _names_non_dev(branch):
        raise NotDevError(f"refusing branch {branch!r}: only dev branches (dev, dev-manual, dev-<name>) are allowed")
    return branch


def check_endpoint(url: str) -> str:
    """Accept only an https URL whose API stage (first path segment) or a host label is exactly 'dev'."""
    parsed = urlparse(url or "")
    if parsed.scheme != "https" or not parsed.hostname:
        raise NotDevError("refusing endpoint: it must be an https URL")
    labels = parsed.hostname.lower().split(".")
    segments = [part for part in parsed.path.lower().split("/") if part]
    if _names_non_dev(*labels, *segments):
        raise NotDevError(f"refusing endpoint host/stage {parsed.hostname}{parsed.path}: it names a non-dev stage")
    if not (segments[:1] == ["dev"] or "dev" in labels):
        raise NotDevError(f"refusing endpoint {parsed.hostname}{parsed.path}: its stage or host is not marked dev")
    return url


def make_test_code(n: int) -> str:
    """The n-th product code the suite may write (9999000 .. 9999999)."""
    if not 0 <= n <= 999:
        raise ValueError("test codes run from 0 to 999")
    return f"{TEST_PREFIX}{n:03d}"


def write_guard(records: Iterable[Mapping]) -> list:
    """Refuse to write any record whose iprcode is not a test code."""
    records = list(records)
    bad = [r.get("iprcode") for r in records if not str(r.get("iprcode", "")).startswith(TEST_PREFIX)]
    if bad or not records:
        raise NotDevError(f"refusing to write non-test records: {bad or 'none given'}")
    return records
