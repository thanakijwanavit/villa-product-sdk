"""Shared setup for the offline test suite (vps-l7s).

Nothing in tests/ may reach AWS or the network:

* Every ``AWS_*`` environment variable is removed when pytest starts and again before
  each test, so boto3 cannot pick up keys, a profile or a region from the environment.
* The autouse ``offline_guard`` fixture blocks botocore API calls and HTTP requests,
  ``requests`` sessions, DNS lookups and IPv4/IPv6 socket connections. A blocked attempt
  raises ``NetworkBlocked`` and is recorded, and the test then errors at teardown, so the
  run fails even when the code under test swallows the exception (products.py has bare
  ``except:`` blocks).

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


# --- no AWS environment ------------------------------------------------------------

def _aws_variables():
    return [name for name in os.environ if name.startswith("AWS_")]


def pytest_configure(config):
    for name in _aws_variables():
        del os.environ[name]


# --- network guard -----------------------------------------------------------------

class NetworkBlocked(RuntimeError):
    """A test tried to reach AWS or the network."""


@pytest.fixture(autouse=True)
def offline_guard(monkeypatch):
    """Block real AWS and network calls; error the test if one was attempted.

    The fixture value is the list of blocked attempts. A test that makes one on purpose
    clears the list after checking it.
    """
    for name in _aws_variables():
        monkeypatch.delenv(name)
    attempts = []

    def block(what):
        attempts.append(what)
        raise NetworkBlocked("offline test suite: blocked " + what)

    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex

    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            block("socket connection to %r" % (address,))
        return real_connect(sock, address)

    def connect_ex(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            block("socket connection to %r" % (address,))
        return real_connect_ex(sock, address)

    def lookup(host, *args, **kwargs):
        block("DNS lookup of %r" % (host,))

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    for name in ("getaddrinfo", "gethostbyname", "gethostbyname_ex"):
        monkeypatch.setattr(socket, name, lookup)

    try:
        import botocore.client
        import botocore.httpsession
    except ImportError:
        pass
    else:
        def api_call(client, operation_name, api_params):
            block("boto3 call %s.%s" % (client.meta.service_model.service_name, operation_name))

        def http_send(session, request):
            block("boto3 HTTP request %s %s" % (request.method, request.url))

        # every boto3 client call goes through BaseClient._make_api_call; other botocore
        # HTTP traffic, such as the instance-metadata lookup a client without credentials
        # makes, goes through URLLib3Session.send
        monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", api_call)
        monkeypatch.setattr(botocore.httpsession.URLLib3Session, "send", http_send)

    try:
        import requests.sessions
    except ImportError:
        pass
    else:  # requests.get/post/... all end in Session.send
        def send(session, request, **kwargs):
            block("requests %s %s" % (request.method, request.url))

        monkeypatch.setattr(requests.sessions.Session, "send", send)

    yield attempts
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
    * ``downloads``: the URLs passed to ``Requests.getContentFromUrl``. ``serve()`` sets
      what each URL returns.
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
        """Make ``Requests.getContentFromUrl(url)`` return ``content``."""
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

    def _download(self, url):
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
                return fake._download(url)

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
