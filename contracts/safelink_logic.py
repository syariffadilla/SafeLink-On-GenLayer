"""Pure, deterministic SafeLink logic.

Stdlib only — no GenLayer imports — so this module is unit-testable with
plain pytest and no GenVM. The contract file ``contracts/safelink.py``
contains byte-identical copies of these four functions (checked by
``tests/test_contract_sync.py``); the contract is self-contained because
a single-file GenLayer contract cannot import a sibling module on-chain.

Design notes (see README.md / CONSENSUS.md for the full story):

* The verdict is a DETERMINISTIC rule over derived signals, not an LLM
  opinion. No LLM is called anywhere in v1. Validators re-derive the
  signals from their own fetch and compare them exactly.
* Only the signal fields listed in ``COMPARED_SIGNAL_KEYS`` are part of
  consensus. ``content_len`` / ``body_sample`` are audit observations
  (pages change between fetches); they are recorded, never compared.
* A password field on its own (plain https login page, clean host) is
  NOT a warning — most legitimate login pages have one. It becomes
  malicious only combined with http, brand impersonation, an IP-literal
  host, or a form posting off-host.
"""

MAX_URL_LEN = 2048
BODY_SAMPLE_LEN = 200

VERDICT_SAFE = "safe"
VERDICT_MALICIOUS = "malicious"
VERDICT_DISPUTED = "disputed"
VERDICT_UNCHECKED = "unchecked"

# Signal fields the validator must agree on exactly. Everything else in
# the signals dict is observation only.
COMPARED_SIGNAL_KEYS = (
    "url",
    "host",
    "status_code",
    "is_https",
    "is_ip_literal",
    "is_punycode",
    "impersonates_brand",
    "has_password_field",
    "off_host_form",
    "blocklisted",
)


def host_of(url):
    """Host part of a URL, lower-cased, without userinfo or port.

    Pure string parsing (no urllib — keeps the contract dependency-free).
    Returns "" for unparseable input.
    """
    if not isinstance(url, str):
        return ""
    rest = url.split("://", 1)[1] if "://" in url else url
    hostport = rest.split("/", 1)[0]
    if "@" in hostport:
        hostport = hostport.split("@", 1)[1]
    host = hostport.split(":", 1)[0]
    return host.lower()


def normalize_url(raw_url):
    """Normalize a URL into its canonical registry key.

    Lower-cases scheme + host only (paths stay case-sensitive), drops the
    fragment, drops a default port (:443 on https, :80 on http), drops a
    trailing "/" on the bare host. Raises ValueError on anything that is
    not an http(s) URL. The contract converts this to gl.UserError.
    """
    if not isinstance(raw_url, str):
        raise ValueError("URL must be a string")
    url = raw_url.strip()
    if not url:
        raise ValueError("empty URL")
    if len(url) > MAX_URL_LEN:
        raise ValueError("URL too long")
    if any(ch.isspace() for ch in url):
        raise ValueError("URL contains whitespace")
    if "://" not in url:
        raise ValueError("URL has no scheme")
    scheme, rest = url.split("://", 1)
    scheme = scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError("only http and https URLs are supported")
    rest = rest.split("#", 1)[0]
    if "/" in rest:
        hostport, path = rest.split("/", 1)
        path = "/" + path
    else:
        hostport, path = rest, ""
    if "@" in hostport:
        hostport = hostport.split("@", 1)[1]
    hostport = hostport.lower()
    if scheme == "https" and hostport.endswith(":443"):
        hostport = hostport[:-4]
    if scheme == "http" and hostport.endswith(":80"):
        hostport = hostport[:-3]
    if not hostport:
        raise ValueError("URL has no host")
    if path == "/":
        path = ""
    return scheme + "://" + hostport + path


def _impersonated_brand(host, brands):
    """Return the brand domain this host impersonates, or "".

    A host impersonates a brand when the brand's base name (e.g.
    "binance" from "binance.com") appears inside one of the host's
    labels, EXCEPT when the host is the brand itself or a subdomain of
    it (www.binance.com, login.binance.com are the brand's own hosts and
    cannot be judged impersonation from the name alone).
    """
    if not host:
        return ""
    for brand in brands:
        base = brand.split(".", 1)[0].lower()
        if not base:
            continue
        if host == brand.lower() or host.endswith("." + brand.lower()):
            continue
        for label in host.split("."):
            if base in label:
                return brand
    return ""


def _is_ip_literal(host):
    """True for dotted-quad IPv4 hosts (e.g. 185.220.101.4)."""
    if not host or host.count(".") != 3:
        return False
    parts = host.split(".")
    for part in parts:
        if not part.isdigit():
            return False
        if not 0 <= int(part) <= 255:
            return False
        if len(part) > 1 and part.startswith("0"):
            return False
    return True


def _off_host_form(body_lower, page_host):
    """True if any form action posts to an http(s) host != page host.

    Deliberately simple substring scan — no HTML parser is available in
    GenVM. Only absolute http(s) actions are considered; relative
    actions post back to the same host by definition.
    """
    for quote in ('"', "'"):
        needle = "action=" + quote + "http"
        start = 0
        while True:
            idx = body_lower.find(needle, start)
            if idx == -1:
                break
            end = body_lower.find(quote, idx + len(needle))
            if end == -1:
                break
            action_url = body_lower[idx + len("action=") + 1 : end]
            if host_of(action_url) and host_of(action_url) != page_host:
                return True
            start = end + 1
    return False


def derive_signals(url, status_code, body, brands, blocked_hosts):
    """Derive the check signals for one fetched page.

    ``url`` must already be normalized, ``body`` is the decoded page
    text. Runs identically on leader and validator; the validator
    compares exactly the COMPARED_SIGNAL_KEYS fields of the result.
    """
    host = host_of(url)
    body_lower = body.lower()
    return {
        "url": url,
        "host": host,
        "status_code": status_code,
        "is_https": url.startswith("https://"),
        "is_ip_literal": _is_ip_literal(host),
        "is_punycode": "xn--" in host,
        "impersonates_brand": _impersonated_brand(host, brands),
        "has_password_field": (
            'type="password"' in body_lower or "type='password'" in body_lower
        ),
        "off_host_form": _off_host_form(body_lower, host),
        "blocklisted": host in blocked_hosts,
        # Observation only — recorded for audit, never compared, because
        # page content changes between the leader's and validators'
        # fetches. The verdict never depends on these two fields.
        "content_len": len(body),
        "body_sample": body[:BODY_SAMPLE_LEN],
    }


def verdict_from_signals(signals):
    """Deterministic verdict rule. Pure function of the signals dict.

    malicious: blocklisted host, OR a password field combined with any
        hard aggravator (plain http, brand impersonation, IP-literal
        host, form posting off-host).
    disputed: any single warning signal on its own (plain http,
        impersonation without a password field, IP-literal or punycode
        host, off-host form) — suspicious, not proven.
    safe: https, status 200, no warning signal at all. A password field
        on its own is not a warning: legitimate login pages have one.
    """
    if signals["blocklisted"]:
        return VERDICT_MALICIOUS
    hard = signals["has_password_field"] and (
        (not signals["is_https"])
        or signals["impersonates_brand"] != ""
        or signals["is_ip_literal"]
        or signals["off_host_form"]
    )
    if hard:
        return VERDICT_MALICIOUS
    warning = (
        (not signals["is_https"])
        or signals["impersonates_brand"] != ""
        or signals["is_ip_literal"]
        or signals["is_punycode"]
        or signals["off_host_form"]
    )
    if warning:
        return VERDICT_DISPUTED
    return VERDICT_SAFE
