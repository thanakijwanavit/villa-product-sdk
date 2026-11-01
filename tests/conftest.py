"""Shared setup for the offline test suite (vps-l7s).

Nothing in tests/ may reach AWS or the network:

* Every ``AWS_*`` environment variable is removed when pytest starts and again before
  each test, so boto3 cannot pick up keys, a profile or a region from the environment,
  and botocore's credential lookup is stubbed to find none, so boto3 never uses the
  caller's own credentials (``~/.aws``, instance metadata) either.
* From pytest_configure to pytest_unconfigure, collection included, a guard in the
  pytest process blocks botocore API calls and HTTP requests, ``requests`` sessions,
  forward and reverse DNS lookups through the ``socket`` module, and IPv4/IPv6
  connections and datagram sends through ``socket.socket``. A blocked attempt raises
  ``NetworkBlocked`` and is recorded. One made during a test errors that test at
  teardown (the autouse ``offline_guard`` fixture); one made outside any test fails the
  run at the end. So the run fails even when the code under test swallows the exception
  (products.py has bare ``except:`` blocks). Not covered: code that uses the C-level
  ``_socket`` module directly, and subprocesses that a test starts, unless they load
  this conftest, as the harness's inner pytest runs do.

The SDK reaches AWS only through ``lambdasdk.lambdasdk.Lambda`` and
``s3bz.s3bz.S3``/``Requests``. The ``load_sdk`` fixture imports an SDK module afresh
with those two packages replaced by the recording fakes of ``fake_aws``, and undoes the
import after the test so the fakes never leak into other tests. Replacing the packages
also keeps these tests independent of the s3bz release: s3bz 0.1.27 does not import on
Python 3.12 (``AttributeError: readonly attribute``, fixed by the pins of vps-b7v).
tests/test_offline_harness.py checks the fakes against the real signatures.
"""
import copy
import importlib
import json
import logging
import os
import socket
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:  # test this checkout, also under a bare `pytest`
    sys.path.insert(0, str(ROOT))

_MISSING = object()


# --- no AWS environment, no network --------------------------------------------------

def _aws_variables():
    return [name for name in os.environ if name.startswith("AWS_")]


class NetworkBlocked(RuntimeError):
    """Something in the test run tried to reach AWS or the network."""


class _Guard:
    """Patches that block real AWS and network calls, and where blocked attempts go.

    ``sink`` is the running test's list (set by offline_guard), else ``outside``.
    """

    def __init__(self):
        self.outside = []
        self.sink = self.outside
        self.patches = pytest.MonkeyPatch()

    def block(self, what):
        self.sink.append(what)
        raise NetworkBlocked("offline test suite: blocked " + what)

    def install(self):
        block, patch = self.block, self.patches.setattr
        inet = (socket.AF_INET, socket.AF_INET6)
        real = {name: getattr(socket.socket, name)
                for name in ("connect", "connect_ex", "sendto", "sendmsg")}

        def connect(sock, address):
            if sock.family in inet:
                block("socket connection to %r" % (address,))
            return real["connect"](sock, address)

        def connect_ex(sock, address):
            if sock.family in inet:
                block("socket connection to %r" % (address,))
            return real["connect_ex"](sock, address)

        def sendto(sock, data, *flags_and_address):
            if sock.family in inet:  # UDP needs no connect
                block("datagram to %r" % (flags_and_address[-1],))
            return real["sendto"](sock, data, *flags_and_address)

        def sendmsg(sock, *args):  # (buffers, ancdata, flags, address)
            if sock.family in inet:
                block("datagram to %r" % (args[3] if len(args) > 3 else "the connected peer",))
            return real["sendmsg"](sock, *args)

        def lookup(host, *args, **kwargs):
            block("DNS lookup of %r" % (host,))

        def reverse_lookup(address, *args, **kwargs):
            block("reverse DNS lookup of %r" % (address,))

        for name, function in (("connect", connect), ("connect_ex", connect_ex),
                               ("sendto", sendto), ("sendmsg", sendmsg)):
            patch(socket.socket, name, function)
        for name in ("getaddrinfo", "gethostbyname", "gethostbyname_ex"):
            patch(socket, name, lookup)
        for name in ("gethostbyaddr", "getnameinfo"):
            patch(socket, name, reverse_lookup)

        try:
            import botocore.client
            import botocore.httpsession
            import botocore.session
        except ImportError:
            pass
        else:
            def api_call(client, operation_name, api_params):
                block("boto3 call %s.%s"
                      % (client.meta.service_model.service_name, operation_name))

            def http_send(session, request):
                block("boto3 HTTP request %s %s" % (request.method, request.url))

            # every boto3 client call goes through BaseClient._make_api_call; any other
            # botocore HTTP traffic goes through URLLib3Session.send
            patch(botocore.client.BaseClient, "_make_api_call", api_call)
            patch(botocore.httpsession.URLLib3Session, "send", http_send)
            # boto3 finds no credentials: no ~/.aws files, no credential_process, no
            # instance-metadata lookup. A client built without keys, as
            # lambdasdk.Lambda(user=None) builds one, is then created offline and never
            # holds real credentials; its calls are still blocked above.
            patch(botocore.session.Session, "get_credentials", lambda session: None)

        try:
            import requests.sessions
        except ImportError:
            pass
        else:  # requests.get/post/... all end in Session.send
            def send(session, request, **kwargs):
                block("requests %s %s" % (request.method, request.url))

            patch(requests.sessions.Session, "send", send)


_GUARD = _Guard()


def pytest_configure(config):
    for name in _aws_variables():
        del os.environ[name]
    _GUARD.install()


def pytest_unconfigure(config):
    _GUARD.patches.undo()


def pytest_sessionfinish(session, exitstatus):
    if _GUARD.outside:  # collection, a session fixture, a hook: no test to fail
        if session.exitstatus == pytest.ExitCode.OK:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter is not None:
            reporter.write_line("offline test suite: blocked outside any test: "
                                + "; ".join(_GUARD.outside), red=True)


@pytest.fixture(autouse=True)
def offline_guard(monkeypatch):
    """Error the test if it tried a real AWS or network call.

    The fixture value is the list of the test's blocked attempts. A test that makes one
    on purpose clears the list after checking it.
    """
    for name in _aws_variables():
        monkeypatch.delenv(name)
    attempts = []
    _GUARD.sink = attempts
    yield attempts
    _GUARD.sink = _GUARD.outside
    if attempts:
        pytest.fail("a test tried to reach AWS or the network: " + "; ".join(attempts),
                    pytrace=False)


# --- fakes for lambdasdk and s3bz ---------------------------------------------------

class UnexpectedCall(AssertionError):
    """The SDK made a call that the test did not set up."""


class FakeAws:
    """Recording stand-ins for ``lambdasdk.lambdasdk`` and ``s3bz.s3bz``.

    * ``clients``: the arguments of every ``Lambda(...)`` the SDK built.
    * ``invocations``: one dict per ``Lambda.invoke`` call, with ``functionName``,
      ``input`` (a copy) and ``invocationType``. ``respond()`` sets the answer. A
      synchronous invoke of a function with no answer set raises ``UnexpectedCall``. An
      ``'Event'`` invoke returns True, as lambdasdk does. An error set with
      ``respond(error=...)`` is raised for both kinds.
    * ``saves``: one dict per ``S3.save`` call, with ``key``, ``objectToSave`` (the object
      itself), ``bucket`` and any keyword arguments, such as ``user`` and ``pw``. Set
      ``fail_saves_with`` to an exception to make saves raise it.
    * ``downloads``: the URLs passed to ``Requests.getContentFromUrl``, or to ``download``
      where a test puts it in place of another downloader. ``serve()`` sets what each URL
      returns.
    * ``calls``: the invokes, saves and downloads in order, as ``(kind, name)`` pairs.
    """

    def __init__(self):
        self.clients, self.invocations, self.saves, self.downloads, self.calls = [], [], [], [], []
        self.fail_saves_with = None
        self._responses, self._contents = {}, {}
        self.modules = self._build_modules()

    def respond(self, function_name, body=None, statusCode=200, raw=_MISSING, error=None):
        """Set how ``function_name`` answers.

        By default it answers with a Lambda proxy response whose ``body`` is JSON, as the
        product Lambdas do. ``raw`` sets the exact response instead. ``error`` makes the
        invoke raise that exception.
        """
        if error is not None:
            self._responses[function_name] = error
        elif raw is not _MISSING:
            self._responses[function_name] = raw
        else:
            self._responses[function_name] = {"statusCode": statusCode, "body": json.dumps(body)}

    def serve(self, url, content):
        """Make ``Requests.getContentFromUrl(url)`` and ``download(url)`` return ``content``."""
        self._contents[url] = content

    def _invoke(self, functionName, input, invocationType):
        self.calls.append(("invoke", functionName))
        self.invocations.append({"functionName": functionName, "input": copy.deepcopy(input),
                                 "invocationType": invocationType})
        response = self._responses.get(functionName, _MISSING)
        if isinstance(response, BaseException):
            raise response
        if invocationType == "Event":
            return True  # lambdasdk returns True for asynchronous invokes
        if response is _MISSING:
            raise UnexpectedCall("Lambda %r was invoked, but the test set no response for it"
                                 % (functionName,))
        return copy.deepcopy(response)  # Response.fromDict pops 'body' from what it is given

    def _save(self, key, objectToSave, bucket, kwargs):
        self.calls.append(("s3.save", key))
        self.saves.append(dict(kwargs, key=key, objectToSave=objectToSave, bucket=bucket))
        if self.fail_saves_with is not None:
            raise self.fail_saves_with
        return True

    def download(self, url):
        """The fake download of ``url``: recorded, answered from ``serve()``."""
        self.calls.append(("download", url))
        self.downloads.append(url)
        if url not in self._contents:
            raise UnexpectedCall("%r was downloaded, but the test served nothing there" % (url,))
        return self._contents[url]

    def _build_modules(self):
        fake = self

        class InvocationType:
            """The values of lambdasdk.lambdasdk.InvocationType."""
            requestResponse = "RequestResponse"
            event = "Event"

        class Lambda:
            def __init__(self, user=None, pw=None, sessionToken=None, region="ap-southeast-1"):
                fake.clients.append({"user": user, "pw": pw, "sessionToken": sessionToken,
                                     "region": region})

            def invoke(self, functionName, input, invocationType="RequestResponse"):
                return fake._invoke(functionName, input, invocationType)

        class S3:
            @classmethod
            def save(cls, key, objectToSave, bucket="", **kwargs):
                return fake._save(key, objectToSave, bucket, kwargs)

        class Requests:
            @staticmethod
            def getContentFromUrl(url):
                return fake.download(url)

        s3bz, s3bz_s3bz = types.ModuleType("s3bz"), types.ModuleType("s3bz.s3bz")
        s3bz_s3bz.S3, s3bz_s3bz.Requests = S3, Requests
        s3bz.s3bz = s3bz_s3bz
        lambdasdk, lambdasdk_lambdasdk = (types.ModuleType("lambdasdk"),
                                          types.ModuleType("lambdasdk.lambdasdk"))
        lambdasdk_lambdasdk.Lambda, lambdasdk_lambdasdk.InvocationType = Lambda, InvocationType
        lambdasdk.lambdasdk = lambdasdk_lambdasdk
        return {"s3bz": s3bz, "s3bz.s3bz": s3bz_s3bz,
                "lambdasdk": lambdasdk, "lambdasdk.lambdasdk": lambdasdk_lambdasdk}


@pytest.fixture
def fake_aws():
    """A fresh FakeAws for the test."""
    return FakeAws()


@pytest.fixture
def load_sdk(fake_aws):
    """Return ``load(name)``, which imports SDK module ``name`` afresh, bound to ``fake_aws``.

    After the test, sys.modules and the parent package's attribute are restored to what
    they were before.
    """
    saved_modules, saved_attributes = {}, []

    def load(name):
        for module_name in list(fake_aws.modules) + [name]:
            saved_modules.setdefault(module_name, sys.modules.get(module_name, _MISSING))
        package_name, _, attribute = name.rpartition(".")
        package = importlib.import_module(package_name)
        saved_attributes.append((package, attribute, vars(package).get(attribute, _MISSING)))
        sys.modules.update(fake_aws.modules)
        sys.modules.pop(name, None)
        root = logging.getLogger()  # the inventory modules call logging.basicConfig
        handlers, level = list(root.handlers), root.level
        try:
            return importlib.import_module(name)
        finally:
            for handler in [h for h in root.handlers if h not in handlers]:
                root.removeHandler(handler)
            root.setLevel(level)

    yield load
    for module_name, module in saved_modules.items():
        if module is _MISSING:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = module
    for package, attribute, value in reversed(saved_attributes):
        if value is _MISSING:
            vars(package).pop(attribute, None)
        else:
            setattr(package, attribute, value)
