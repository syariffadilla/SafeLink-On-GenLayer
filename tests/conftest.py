"""Test harness: a minimal fake ``genlayer`` module.

The real GenLayer SDK / GenVM runner is NOT installed here (see
TEST_LOG.md for the install attempt), so the contract is loaded with this
stub. The stub emulates the documented semantics just enough to exercise
the contract end to end off-chain:

* ``@gl.public.view`` / ``@gl.public.write`` are identity decorators.
* ``gl.message.sender_address`` is a settable attribute (the caller).
* ``gl.nondet.web.get(url)`` serves canned responses from
  ``WEB_RESPONSES`` and records every call in ``WEB_CALLS``.
* ``gl.vm.run_nondet_unsafe(leader_fn, validator_fn)`` calls the leader,
  wraps the result in ``gl.vm.Return``, calls the validator, and returns
  the leader's value only if the validator agrees. Disagreement (or a
  leader error the validator does not agree with) raises RuntimeError —
  the stub's emulation of "transaction undetermined, no state change".
* ``TreeMap`` / ``DynArray`` are dict / list subclasses; ``u64`` etc.
  are plain ``int``; ``Address`` is ``str``.

These are DIRECT-mode tests in GrantFlow's sense (tests/direct):
they prove the contract's logic, state machine and validator
agreement — they do NOT prove the contract passes GenVM lint or Studio
consensus. That step is still open; see README.md / TEST_LOG.md.
"""

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = ROOT / "contracts"
sys.path.insert(0, str(CONTRACTS_DIR))

import safelink_logic  # noqa: E402  (pure logic, no GenLayer import)

# ---------------------------------------------------------------- fake gl

WEB_RESPONSES = {}
WEB_CALLS = []


class _FakeResponse:
    def __init__(self, status, body):
        # Mirrors the real SDK Response dataclass: fields are `status`
        # (not `status_code`) and `body` (bytes).
        self.status = status
        self.body = body.encode("utf-8") if isinstance(body, str) else body


class _FakeWeb:
    @staticmethod
    def get(url):
        WEB_CALLS.append(url)
        if url not in WEB_RESPONSES:
            return _FakeResponse(404, "not found")
        value = WEB_RESPONSES[url]
        if isinstance(value, list):
            # Consumed in order: lets tests change the page between the
            # leader's fetch and the validator's re-fetch.
            status_code, body = value.pop(0)
        else:
            status_code, body = value
        return _FakeResponse(status_code, body)


class _UserError(Exception):
    pass


class _VMError(Exception):
    pass


class _Return:
    def __init__(self, calldata):
        self.calldata = calldata


class _LeaderError:
    """Non-Return result: the leader raised instead of returning."""

    def __init__(self, error):
        self.error = error


def _run_nondet_unsafe(leader_fn, validator_fn):
    try:
        value = leader_fn()
    except Exception as exc:  # leader raised (e.g. gl.UserError on 404)
        agreed = validator_fn(_LeaderError(exc))
        if agreed:
            raise exc
        raise RuntimeError("consensus failed: leader error not agreed")
    if validator_fn(_Return(value)):
        return value
    raise RuntimeError("consensus failed: validator disagreed")


def _make_fake_genlayer():
    fake = types.ModuleType("genlayer")

    class _TreeMap(dict):
        def __class_getitem__(cls, item):
            return cls

    class _DynArray(list):
        def __class_getitem__(cls, item):
            return cls

    def _storage_default(annotation):
        # Emulates GenVM: storage fields declared as class-level
        # annotations start initialized (maps empty, lists empty,
        # numbers 0, bools False, strings "").
        if annotation is _TreeMap:
            return {}
        if annotation is _DynArray:
            return []
        if annotation is int:
            return 0
        if annotation is bool:
            return False
        if annotation is str:
            return ""
        return None

    class _ContractBase:
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__(**kwargs)
            orig_init = cls.__init__

            def wrapped_init(self, *args, **kwargs):
                for name, ann in cls.__annotations__.items():
                    setattr(self, name, _storage_default(ann))
                orig_init(self, *args, **kwargs)

            cls.__init__ = wrapped_init

    class _Public:
        @staticmethod
        def view(fn):
            return fn

        @staticmethod
        def write(fn):
            return fn

    class _Message:
        sender_address = "0x00000000000000000000000000000000000000A1"

    fake.public = _Public()
    fake.message = _Message()
    fake.UserError = _UserError
    fake.VMError = _VMError
    # Identity decorator: marks a class usable as a storage value in
    # the real SDK (@allow_storage). The stub needs no behaviour.
    fake.allow_storage = lambda cls: cls
    fake.Contract = _ContractBase
    fake.Address = str
    fake.TreeMap = _TreeMap
    fake.DynArray = _DynArray
    fake.u64 = int
    fake.u256 = int
    fake.u32 = int
    fake.i32 = int
    fake.i64 = int
    fake.vm = types.SimpleNamespace(
        Return=_Return,
        Result=_Return,
        UserError=_UserError,
        VMError=_VMError,
        run_nondet_unsafe=_run_nondet_unsafe,
    )
    fake.nondet = types.SimpleNamespace(web=_FakeWeb())
    # Contracts do `from genlayer import *` and then use `gl.*`: the real
    # SDK exposes the `gl` namespace that way, so the stub must too.
    fake.gl = fake
    fake.__all__ = [
        "gl",
        "allow_storage",
        "Contract",
        "public",
        "message",
        "UserError",
        "VMError",
        "Address",
        "TreeMap",
        "DynArray",
        "u64",
        "u256",
        "u32",
        "i32",
        "i64",
        "vm",
        "nondet",
    ]
    return fake


def load_contract():
    """Load contracts/safelink.py with the fake genlayer module."""
    fake = _make_fake_genlayer()
    sys.modules["genlayer"] = fake
    spec = importlib.util.spec_from_file_location(
        "safelink_contract", CONTRACTS_DIR / "safelink.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, fake


def reset_web():
    WEB_RESPONSES.clear()
    WEB_CALLS.clear()


def set_sender(fake, address):
    fake.message.sender_address = address


ADMIN = "0x00000000000000000000000000000000000000A1"
OTHER = "0x00000000000000000000000000000000000000B2"
