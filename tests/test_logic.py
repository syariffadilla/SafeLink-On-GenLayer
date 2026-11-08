"""Pure-logic tests: no GenLayer stub needed, plain pytest."""

import pytest

from safelink_logic import (
    derive_signals,
    host_of,
    normalize_url,
    verdict_from_signals,
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
BRANDS = ["binance.com", "metamask.io", "genlayer.com"]


# -- normalize_url ------------------------------------------------------


def test_normalize_lowercases_scheme_and_host_only():
    assert (
        normalize_url("HTTPS://Example.COM/Path/To/Page")
        == "https://example.com/Path/To/Page"
    )


def test_normalize_drops_fragment_default_port_and_root_slash():
    assert normalize_url("https://example.com:443/a#section") == (
        "https://example.com/a"
    )
    assert normalize_url("http://example.com:80/") == "http://example.com"
    assert normalize_url("https://example.com/") == "https://example.com"


def test_normalize_keeps_query_and_non_root_trailing_slash():
    assert (
        normalize_url("https://example.com/a/b/?x=1")
        == "https://example.com/a/b/?x=1"
    )


@pytest.mark.parametrize(
    "bad",
    ["", "   ", "not a url", "ftp://example.com/x", "example.com/x",
     "https://", "https://exa mple.com/", "http://exam ple.com"],
)
def test_normalize_rejects(bad):
    with pytest.raises(ValueError):
        normalize_url(bad)


def test_normalize_rejects_too_long():
    with pytest.raises(ValueError):
        normalize_url("https://example.com/" + "a" * 2100)


# -- host_of ------------------------------------------------------------


def test_host_of_strips_userinfo_port_and_case():
    assert host_of("https://User:pass@Sub.Example.COM:8443/a") == (
        "sub.example.com"
    )
    assert host_of("http://185.220.101.4/login") == "185.220.101.4"
    assert host_of("garbage") == "garbage"


# -- verdict rule ---------------------------------------------------------


def _signals(**overrides):
    base = {
        "url": "https://example.com/",
        "host": "example.com",
        "status_code": 200,
        "is_https": True,
        "is_ip_literal": False,
        "is_punycode": False,
        "impersonates_brand": "",
        "has_password_field": False,
        "off_host_form": False,
        "blocklisted": False,
        "content_len": 10,
        "body_sample": "x",
    }
    base.update(overrides)
    return base


def test_verdict_safe_clean_https_page():
    assert verdict_from_signals(_signals()) == "safe"


def test_verdict_safe_password_field_alone_is_not_a_warning():
    # A legitimate login page has a password field. Flagging it would
    # be a false positive — the field only matters with an aggravator.
    assert verdict_from_signals(_signals(has_password_field=True)) == "safe"


def test_verdict_malicious_blocklisted():
    assert verdict_from_signals(_signals(blocklisted=True)) == "malicious"


@pytest.mark.parametrize(
    "overrides",
    [
        {"has_password_field": True, "is_https": False},
        {"has_password_field": True, "impersonates_brand": "binance.com"},
        {"has_password_field": True, "is_ip_literal": True},
        {"has_password_field": True, "off_host_form": True},
    ],
)
def test_verdict_malicious_password_plus_aggravator(overrides):
    assert verdict_from_signals(_signals(**overrides)) == "malicious"


@pytest.mark.parametrize(
    "overrides",
    [
        {"is_https": False},
        {"impersonates_brand": "binance.com"},
        {"is_ip_literal": True},
        {"is_punycode": True},
        {"off_host_form": True},
    ],
)
def test_verdict_disputed_single_warning(overrides):
    assert verdict_from_signals(_signals(**overrides)) == "disputed"


# -- derive_signals -------------------------------------------------------


def test_derive_legit_page_is_safe():
    signals = derive_signals(
        "https://example.com/", 200, LEGIT_BODY, BRANDS, []
    )
    assert signals["host"] == "example.com"
    assert signals["is_https"] is True
    assert signals["has_password_field"] is False
    assert signals["off_host_form"] is False
    assert verdict_from_signals(signals) == "safe"


def test_derive_phishing_page_is_malicious():
    signals = derive_signals(
        "https://binance-secure-login.com/login",
        200,
        PHISH_BODY,
        BRANDS,
        [],
    )
    assert signals["impersonates_brand"] == "binance.com"
    assert signals["has_password_field"] is True
    assert signals["off_host_form"] is True
    assert verdict_from_signals(signals) == "malicious"


def test_derive_http_login_is_malicious():
    signals = derive_signals(
        "http://example.com/login", 200, LOGIN_BODY, BRANDS, []
    )
    assert verdict_from_signals(signals) == "malicious"


def test_derive_punycode_is_disputed():
    signals = derive_signals(
        "https://xn--bnance-9ya.com/", 200, LEGIT_BODY, BRANDS, []
    )
    assert signals["is_punycode"] is True
    assert verdict_from_signals(signals) == "disputed"


def test_derive_brand_subdomain_is_not_impersonation():
    signals = derive_signals(
        "https://login.binance.com/", 200, LEGIT_BODY, BRANDS, []
    )
    assert signals["impersonates_brand"] == ""
    assert verdict_from_signals(signals) == "safe"
    signals = derive_signals(
        "https://www.binance.com/", 200, LEGIT_BODY, BRANDS, []
    )
    assert signals["impersonates_brand"] == ""


def test_derive_brand_inside_other_domain_is_impersonation():
    for host in (
        "binance.com.evil.example",
        "mybinance.example",
        "secure-binance.example",
    ):
        signals = derive_signals(
            "https://" + host + "/", 200, LEGIT_BODY, BRANDS, []
        )
        assert signals["impersonates_brand"] == "binance.com", host


def test_derive_ip_literal_host():
    signals = derive_signals(
        "https://185.220.101.4/", 200, LEGIT_BODY, BRANDS, []
    )
    assert signals["is_ip_literal"] is True
    assert verdict_from_signals(signals) == "disputed"


def test_derive_blocklisted_host_is_malicious():
    signals = derive_signals(
        "https://evil.example/", 200, LEGIT_BODY, BRANDS, ["evil.example"]
    )
    assert signals["blocklisted"] is True
    assert verdict_from_signals(signals) == "malicious"


def test_derive_relative_form_action_is_not_off_host():
    body = (
        '<html><body><form action="/login">'
        '<input type="password" name="p"></form></body></html>'
    )
    signals = derive_signals(
        "https://example.com/login", 200, body, BRANDS, []
    )
    assert signals["off_host_form"] is False
    assert verdict_from_signals(signals) == "safe"
