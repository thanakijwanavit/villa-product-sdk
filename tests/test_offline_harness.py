"""Checks on the offline harness in conftest.py (vps-l7s).

The guard really blocks boto3, requests, forward and reverse DNS lookups, socket
connections and datagrams. It fails the run even when the code under test swallows the
error, and also when the attempt is made outside any test (here, at import during
collection). A run started with AWS_* set sees none. load_sdk leaves nothing behind,
and the fakes keep the signatures of the installed lambdasdk and s3bz.
"""
import ast
import importlib.util
import inspect
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
_MISSING = object()


def test_no_aws_variables_during_tests():
    assert [name for name in os.environ if name.startswith("AWS_")] == []


def test_a_real_boto3_call_is_blocked(offline_guard):
    boto3 = pytest.importorskip("boto3")
    client = boto3.client("lambda", region_name="ap-southeast-1",
                          aws_access_key_id="not-a-key", aws_secret_access_key="not-a-secret")
    with pytest.raises(Exception, match="blocked boto3 call lambda.Invoke"):
        client.invoke(FunctionName="product-get-dev-manual", Payload=b"{}")
    assert offline_guard == ["boto3 call lambda.Invoke"]
    offline_guard.clear()  # blocked on purpose


def test_a_client_without_keys_is_built_offline_and_finds_no_credentials(offline_guard):
    """What lambdasdk.Lambda(user=None, pw=None) builds, as a real ProductSdk() does."""
    boto3 = pytest.importorskip("boto3")
    client = boto3.client("lambda", region_name="ap-southeast-1")
    assert offline_guard == []  # no instance-metadata lookup, no ~/.aws credentials
    assert boto3.session.Session().get_credentials() is None
    with pytest.raises(Exception, match="blocked boto3 call lambda.Invoke"):
        client.invoke(FunctionName="product-get-dev-manual", Payload=b"{}")
    assert offline_guard == ["boto3 call lambda.Invoke"]
    offline_guard.clear()


def test_a_real_requests_call_is_blocked(offline_guard):
    requests = pytest.importorskip("requests")
    with pytest.raises(Exception, match="blocked requests GET https://example.invalid/"):
        requests.get("https://example.invalid/", timeout=1)
    assert offline_guard == ["requests GET https://example.invalid/"]
    offline_guard.clear()


def test_dns_and_sockets_are_blocked(offline_guard):
    with pytest.raises(Exception, match="blocked DNS lookup of 'example.invalid'"):
        socket.create_connection(("example.invalid", 443), timeout=1)
    with pytest.raises(Exception, match="blocked reverse DNS lookup of '192.0.2.1'"):
        socket.gethostbyaddr("192.0.2.1")  # TEST-NET-1: documentation only, not routed
    with pytest.raises(Exception, match="blocked reverse DNS lookup"):
        socket.getnameinfo(("192.0.2.1", 443), 0)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        with pytest.raises(Exception, match="blocked socket connection"):
            sock.connect(("192.0.2.1", 443))
    assert len(offline_guard) == 4
    offline_guard.clear()


def test_datagrams_are_blocked(offline_guard):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:  # UDP needs no connect
        with pytest.raises(Exception, match="blocked datagram to"):
            sock.sendto(b"x", ("192.0.2.1", 53))
        with pytest.raises(Exception, match="blocked datagram to"):
            sock.sendmsg([b"x"], [], 0, ("192.0.2.1", 53))
    assert offline_guard == ["datagram to ('192.0.2.1', 53)"] * 2
    offline_guard.clear()


def run_pytest(directory, tests, extra_env=None):
    """Run pytest in a subprocess on ``tests`` (file name: source) with this conftest."""
    (directory / "pytest.ini").write_text("[pytest]\n")
    (directory / "conftest.py").write_text((HERE / "conftest.py").read_text(encoding="utf-8"))
    for name, source in tests.items():
        (directory / name).write_text(source)
    env = dict(os.environ, **(extra_env or {}))
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(ROOT), os.environ.get("PYTHONPATH")]))
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(directory)],
        cwd=str(directory), env=env, capture_output=True, text=True, timeout=300)
    return result.returncode, result.stdout + result.stderr


INNER_TESTS = '''
import os
import sys

import boto3


def test_sees_no_aws_variables():
    assert [name for name in os.environ if name.startswith("AWS_")] == []


def test_swallowed_real_call():
    try:
        boto3.client("lambda", region_name="ap-southeast-1", aws_access_key_id="not-a-key",
                     aws_secret_access_key="not-a-secret").invoke(
            FunctionName="offline-guard-check-never-deployed")
    except Exception:
        pass  # swallowed, as the bare except: blocks in products.py do


def test_load_sdk_binds_the_fakes(load_sdk, fake_aws):
    products = load_sdk("villaProductSdk.products")
    assert products.Lambda is fake_aws.modules["lambdasdk.lambdasdk"].Lambda


def test_load_sdk_left_nothing_behind():
    import villaProductSdk
    assert "villaProductSdk.products" not in sys.modules
    assert not hasattr(villaProductSdk, "products")
    for name in ("s3bz", "s3bz.s3bz", "lambdasdk", "lambdasdk.lambdasdk"):
        module = sys.modules.get(name)
        assert module is None or getattr(module, "__file__", None), name + " is still a fake"
'''


def test_the_guard_fails_the_run_and_a_run_sees_no_aws_variables(tmp_path):
    pytest.importorskip("boto3")
    returncode, output = run_pytest(tmp_path, {"test_inner.py": INNER_TESTS}, {
        "AWS_ACCESS_KEY_ID": "not-a-key", "AWS_SECRET_ACCESS_KEY": "not-a-secret",
        "AWS_PROFILE": "not-a-profile"})
    assert returncode == 1, output
    # the swallowing test passes its call phase and errors at teardown
    assert "4 passed, 1 error" in output, output
    assert "ERROR at teardown of test_swallowed_real_call" in output, output
    assert "a test tried to reach AWS or the network: boto3 call lambda.Invoke" in output, output


SWALLOWED_AT_IMPORT = '''
import socket

try:  # runs during collection, before any test
    socket.getaddrinfo("example.invalid", 443)
except Exception:
    pass


def test_passes():
    pass
'''


def test_a_blocked_call_outside_any_test_fails_the_run(tmp_path):
    returncode, output = run_pytest(tmp_path, {"test_inner.py": SWALLOWED_AT_IMPORT})
    assert returncode == 1, output
    assert "1 passed" in output, output
    assert "blocked outside any test: DNS lookup of 'example.invalid'" in output, output


# --- the fakes keep the signatures of the real libraries -----------------------------

def installed_member(module_name, class_name, member):
    """The AST node of ``class_name.member`` in the installed source of ``module_name``.

    The source is parsed, not imported: s3bz 0.1.27 fails to import on Python 3.12.
    """
    try:
        spec = importlib.util.find_spec(module_name)
    except ImportError:
        spec = None
    if spec is None or not spec.origin:
        pytest.skip(module_name + " is not installed")
    tree = ast.parse(Path(spec.origin).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if getattr(item, "name", None) == member:
                    return item
                if isinstance(item, ast.Assign) and any(
                        getattr(target, "id", None) == member for target in item.targets):
                    return item
    pytest.fail("%s.%s not found in %s" % (class_name, member, spec.origin))


def source_parameters(function):
    args = function.args
    positional = list(getattr(args, "posonlyargs", [])) + list(args.args)
    defaults = [_MISSING] * (len(positional) - len(args.defaults)) + [
        ast.literal_eval(d) for d in args.defaults]
    parameters = [(a.arg, d) for a, d in zip(positional, defaults)]
    if args.vararg:
        parameters.append(("*" + args.vararg.arg, _MISSING))
    for a, d in zip(args.kwonlyargs, args.kw_defaults):
        parameters.append((a.arg, _MISSING if d is None else ast.literal_eval(d)))
    if args.kwarg:
        parameters.append(("**" + args.kwarg.arg, _MISSING))
    return parameters


def fake_parameters(function):
    parameters = []
    for p in inspect.signature(function).parameters.values():
        prefix = {p.VAR_POSITIONAL: "*", p.VAR_KEYWORD: "**"}.get(p.kind, "")
        parameters.append((prefix + p.name, _MISSING if p.default is p.empty else p.default))
    return parameters


@pytest.mark.parametrize("module, cls, member", [
    ("lambdasdk.lambdasdk", "Lambda", "__init__"),
    ("lambdasdk.lambdasdk", "Lambda", "invoke"),
    ("s3bz.s3bz", "S3", "save"),
    ("s3bz.s3bz", "Requests", "getContentFromUrl"),
])
def test_fake_signatures_match_the_installed_library(fake_aws, module, cls, member):
    fake = inspect.getattr_static(getattr(fake_aws.modules[module], cls), member)
    fake = getattr(fake, "__func__", fake)  # unwrap classmethod and staticmethod
    assert fake_parameters(fake) == source_parameters(installed_member(module, cls, member))


@pytest.mark.parametrize("name", ["requestResponse", "event"])
def test_fake_invocation_types_match_lambdasdk(fake_aws, name):
    real = ast.literal_eval(installed_member("lambdasdk.lambdasdk", "InvocationType", name).value)
    assert getattr(fake_aws.modules["lambdasdk.lambdasdk"].InvocationType, name) == real
