# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""SafeLink Registry — a shared, consensus-checked registry of safe /
malicious / disputed URLs for wallets, forums and bots.

One URL, one entry. Any account can ask the contract to check a URL; the
leader fetches the page, every validator independently re-fetches it and
re-derives the same signals, and a verdict is written ONLY when they
agree exactly on the compared signal fields. Disagreement means no
write (the transaction goes undetermined) — a disputed or malicious
verdict is never written on one node's word alone, and a URL is never
auto-marked safe on disagreement.

The verdict is a DETERMINISTIC rule over derived signals (see
verdict_from_signals). No LLM is called anywhere in v1: phishing
detection here is checkable facts (scheme, host shape, brand
impersonation, password field, off-host form, admin blocklist), not an
LLM opinion. That is the whole point of the primitive — the same URL
checked twice gives the same verdict, and any reviewer can re-derive it
by hand from the stored evidence.

Target: stable Studionet, GenVM runner py-genlayer v0.2.5
(1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6). See VERSIONS.md
for how that hash was verified on 2026-11-07 and for the Consensus v0.6
preview split. Do NOT deploy this file to Studio-dev / v0.6 without
re-pinning the header.

The four pure functions below (host_of, normalize_url, derive_signals,
verdict_from_signals) are byte-identical copies of
contracts/safelink_logic.py, which is unit-tested with plain pytest.
They are duplicated here because a single-file GenLayer contract cannot
import a sibling module on-chain. tests/test_contract_sync.py fails the
build if the copies drift.
"""

from genlayer import *

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

# Brands whose lookalike domains are the classic phishing target set for
# this registry's users (crypto wallets / exchanges / GenLayer itself).
# The admin can add or remove brands after deployment.
DEFAULT_BRANDS = [
    "binance.com",
    "metamask.io",
    "genlayer.com",
    "pancakeswap.finance",
    "trustwallet.com",
    "okx.com",
    "coinbase.com",
    "kraken.com",
    "ledger.com",
    "trezor.io",
    "github.com",
    "google.com",
]

DEFAULT_TTL_CHECKS = 1000
MAX_LIST_LIMIT = 100


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


from genlayer import allow_storage


@allow_storage
class Entry:
    """One registry entry. Stored as the value of TreeMap[str, Entry]."""

    url: str
    verdict: str
    status_code: u64
    host: str
    is_https: bool
    is_ip_literal: bool
    is_punycode: bool
    impersonates_brand: str
    has_password_field: bool
    off_host_form: bool
    blocklisted: bool
    content_len: u64
    body_sample: str
    checked_seq: u64
    disputes: u64
    last_dispute_reason: str

    def __init__(
        self,
        url="",
        verdict="unchecked",
        status_code=0,
        host="",
        is_https=False,
        is_ip_literal=False,
        is_punycode=False,
        impersonates_brand="",
        has_password_field=False,
        off_host_form=False,
        blocklisted=False,
        content_len=0,
        body_sample="",
        checked_seq=0,
        disputes=0,
        last_dispute_reason="",
    ):
        self.url = url
        self.verdict = verdict
        self.status_code = status_code
        self.host = host
        self.is_https = is_https
        self.is_ip_literal = is_ip_literal
        self.is_punycode = is_punycode
        self.impersonates_brand = impersonates_brand
        self.has_password_field = has_password_field
        self.off_host_form = off_host_form
        self.blocklisted = blocklisted
        self.content_len = content_len
        self.body_sample = body_sample
        self.checked_seq = checked_seq
        self.disputes = disputes
        self.last_dispute_reason = last_dispute_reason


class SafeLinkRegistry(gl.Contract):
    admin: Address
    entries: TreeMap[str, Entry]
    entry_order: DynArray[str]
    brands: DynArray[str]
    blocked_hosts: DynArray[str]
    # DynArray has no verified remove/clear, so removal is a tombstone:
    # the name stays in the list but is filtered out of every snapshot.
    # TreeMap.get is the verified lookup used for the tombstones.
    disabled_brands: TreeMap[str, bool]
    disabled_hosts: TreeMap[str, bool]
    check_count: u64
    safe_count: u64
    malicious_count: u64
    disputed_count: u64
    total_disputes: u64
    ttl_checks: u64

    def __init__(self):
        self.admin = gl.message.sender_address
        for brand in DEFAULT_BRANDS:
            self.brands.append(brand)
        self.check_count = 0
        self.safe_count = 0
        self.malicious_count = 0
        self.disputed_count = 0
        self.total_disputes = 0
        self.ttl_checks = DEFAULT_TTL_CHECKS

    # -- internal helpers (deterministic, no nondet calls) ------------

    def _require_admin(self):
        if gl.message.sender_address != self.admin:
            raise gl.UserError("SafeLink: only admin")

    def _normalize_or_raise(self, raw_url: str) -> str:
        try:
            return normalize_url(raw_url)
        except ValueError as exc:
            raise gl.UserError("SafeLink: invalid URL: " + str(exc))

    def _is_fresh(self, entry: Entry) -> bool:
        if entry.verdict == VERDICT_DISPUTED:
            return False
        return (self.check_count - entry.checked_seq) < self.ttl_checks

    def _increment_counter(self, verdict: str):
        if verdict == VERDICT_SAFE:
            self.safe_count += 1
        elif verdict == VERDICT_MALICIOUS:
            self.malicious_count += 1
        elif verdict == VERDICT_DISPUTED:
            self.disputed_count += 1

    def _decrement_counter(self, verdict: str):
        if verdict == VERDICT_SAFE and self.safe_count > 0:
            self.safe_count -= 1
        elif verdict == VERDICT_MALICIOUS and self.malicious_count > 0:
            self.malicious_count -= 1
        elif verdict == VERDICT_DISPUTED and self.disputed_count > 0:
            self.disputed_count -= 1

    def _entry_dict(self, entry: Entry, cached: bool = False) -> dict:
        return {
            "url": entry.url,
            "verdict": entry.verdict,
            "fresh": self._is_fresh(entry),
            "cached": cached,
            "status_code": entry.status_code,
            "host": entry.host,
            "is_https": entry.is_https,
            "is_ip_literal": entry.is_ip_literal,
            "is_punycode": entry.is_punycode,
            "impersonates_brand": entry.impersonates_brand,
            "has_password_field": entry.has_password_field,
            "off_host_form": entry.off_host_form,
            "blocklisted": entry.blocklisted,
            "content_len": entry.content_len,
            "body_sample": entry.body_sample,
            "checked_seq": entry.checked_seq,
            "disputes": entry.disputes,
            "last_dispute_reason": entry.last_dispute_reason,
        }

    def _dispute(self, normalized: str, reason: str) -> dict:
        entry = self.entries.get(normalized, None)
        if entry is None:
            raise gl.UserError("SafeLink: unknown URL")
        if entry.verdict != VERDICT_DISPUTED:
            self._decrement_counter(entry.verdict)
            entry.verdict = VERDICT_DISPUTED
            self.disputed_count += 1
        entry.disputes += 1
        entry.last_dispute_reason = reason[:200]
        self.total_disputes += 1
        self.entries[normalized] = entry
        return self._entry_dict(entry)

    def _active_brands(self):
        return [
            b for b in self.brands if not self.disabled_brands.get(b, False)
        ]

    def _active_blocked(self):
        return [
            h for h in self.blocked_hosts if not self.disabled_hosts.get(h, False)
        ]

    def _brands_dict(self) -> dict:
        return {"brands": self._active_brands()}

    def _verdict_dict(self, normalized: str) -> dict:
        entry = self.entries.get(normalized, None)
        if entry is None:
            return {
                "url": normalized,
                "verdict": VERDICT_UNCHECKED,
                "fresh": False,
                "cached": False,
            }
        return self._entry_dict(entry)

    # -- views ---------------------------------------------------------

    @gl.public.view
    def get_verdict(self, url: str) -> dict:
        normalized = self._normalize_or_raise(url)
        return self._verdict_dict(normalized)

    @gl.public.view
    def get_entry(self, url: str) -> dict:
        normalized = self._normalize_or_raise(url)
        return self._verdict_dict(normalized)

    @gl.public.view
    def is_safe(self, url: str) -> bool:
        normalized = self._normalize_or_raise(url)
        entry = self.entries.get(normalized, None)
        if entry is None:
            return False
        return entry.verdict == VERDICT_SAFE and self._is_fresh(entry)

    @gl.public.view
    def list_entries(self, offset: u64, limit: u64) -> dict:
        total = len(self.entry_order)
        if limit == 0 or limit > MAX_LIST_LIMIT:
            limit = MAX_LIST_LIMIT
        result = []
        if offset < total:
            i = total - offset
            count = 0
            while i > 0 and count < limit:
                i -= 1
                key = self.entry_order[i]
                entry = self.entries.get(key, None)
                if entry is not None:
                    result.append(self._entry_dict(entry))
                    count += 1
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "entries": result,
        }

    @gl.public.view
    def get_stats(self) -> dict:
        return {
            "total_entries": len(self.entry_order),
            "check_count": self.check_count,
            "safe": self.safe_count,
            "malicious": self.malicious_count,
            "disputed": self.disputed_count,
            "total_disputes": self.total_disputes,
            "ttl_checks": self.ttl_checks,
            "brands": self._active_brands(),
            "blocked_hosts": self._active_blocked(),
            "admin": str(self.admin),
        }

    @gl.public.view
    def get_brands(self) -> dict:
        return self._brands_dict()

    @gl.public.view
    def is_blocked(self, host: str) -> bool:
        return host.lower() in self._active_blocked()

    # -- writes: checking ----------------------------------------------

    @gl.public.write
    def check_url(self, url: str) -> dict:
        normalized = self._normalize_or_raise(url)
        existing = self.entries.get(normalized, None)
        # Fresh, non-disputed entries are returned without a new
        # consensus round. Disputed entries always re-check.
        if existing is not None and self._is_fresh(existing):
            return self._entry_dict(existing, cached=True)

        # Snapshot consensus inputs BEFORE the nondet block. Storage is
        # never read or written inside leader_fn / validator_fn.
        brands = self._active_brands()
        blocked = self._active_blocked()

        def leader_fn():
            response = gl.nondet.web.get(normalized)
            # NOTE: the live docs page shows `response.status_code`, but
            # the real SDK (py-lib-genlayer-std v0.2.16, Response
            # dataclass) exposes the field as `response.status`, and
            # `body` may be None. The docs are wrong here; the SDK wins.
            # See VERSIONS.md.
            if response.status != 200:
                raise gl.UserError(
                    "SafeLink: fetch failed with status "
                    + str(response.status)
                )
            # Real GenVM returns bytes (or None); be defensive if a test
            # harness hands back str instead.
            raw_body = response.body or b""
            if isinstance(raw_body, bytes):
                body = raw_body.decode("utf-8", "ignore")
            else:
                body = str(raw_body)
            return derive_signals(
                normalized, response.status, body, brands, blocked
            )

        def validator_fn(leaders_res):
            # Leader errors are not agreed on in v1: a failed fetch
            # disagrees and retries with another leader instead of
            # writing anything. See CONSENSUS.md.
            if not isinstance(leaders_res, gl.vm.Return):
                return False
            mine = leader_fn()
            leader = leaders_res.calldata
            for key in COMPARED_SIGNAL_KEYS:
                if mine.get(key) != leader.get(key):
                    return False
            return True

        signals = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        verdict = verdict_from_signals(signals)

        self.check_count += 1
        entry = Entry(
            url=normalized,
            verdict=verdict,
            status_code=signals["status_code"],
            host=signals["host"],
            is_https=signals["is_https"],
            is_ip_literal=signals["is_ip_literal"],
            is_punycode=signals["is_punycode"],
            impersonates_brand=signals["impersonates_brand"],
            has_password_field=signals["has_password_field"],
            off_host_form=signals["off_host_form"],
            blocklisted=signals["blocklisted"],
            content_len=signals["content_len"],
            body_sample=signals["body_sample"],
            checked_seq=self.check_count,
            disputes=0 if existing is None else existing.disputes,
            last_dispute_reason=(
                "" if existing is None else existing.last_dispute_reason
            ),
        )
        if existing is None:
            self.entry_order.append(normalized)
        else:
            self._decrement_counter(existing.verdict)
        self._increment_counter(verdict)
        self.entries[normalized] = entry
        return self._entry_dict(entry)

    # -- writes: disputes -----------------------------------------------

    @gl.public.write
    def dispute_url(self, url: str, reason: str) -> dict:
        normalized = self._normalize_or_raise(url)
        return self._dispute(normalized, reason)

    @gl.public.write
    def request_recheck(self, url: str) -> dict:
        normalized = self._normalize_or_raise(url)
        return self._dispute(normalized, "recheck requested")

    # -- writes: admin ---------------------------------------------------

    @gl.public.write
    def add_brand(self, domain: str) -> dict:
        self._require_admin()
        domain = domain.strip().lower()
        if not domain:
            raise gl.UserError("SafeLink: empty brand domain")
        if domain not in [b for b in self.brands]:
            self.brands.append(domain)
        # Re-adding a previously removed brand clears its tombstone.
        self.disabled_brands[domain] = False
        return self._brands_dict()

    @gl.public.write
    def remove_brand(self, domain: str) -> dict:
        self._require_admin()
        domain = domain.strip().lower()
        if domain not in [b for b in self.brands]:
            raise gl.UserError("SafeLink: unknown brand")
        # Tombstone, not a physical remove: DynArray has no verified
        # remove/clear/pop. The brand stays in the list but is filtered
        # out of every snapshot by _active_brands().
        self.disabled_brands[domain] = True
        return self._brands_dict()

    @gl.public.write
    def block_host(self, host: str) -> dict:
        self._require_admin()
        host = host.strip().lower()
        if not host:
            raise gl.UserError("SafeLink: empty host")
        if host not in [h for h in self.blocked_hosts]:
            self.blocked_hosts.append(host)
        self.disabled_hosts[host] = False
        return {
            "blocked_hosts": self._active_blocked(),
        }

    @gl.public.write
    def unblock_host(self, host: str) -> dict:
        self._require_admin()
        host = host.strip().lower()
        if host not in [h for h in self.blocked_hosts]:
            raise gl.UserError("SafeLink: unknown blocked host")
        self.disabled_hosts[host] = True
        return {
            "blocked_hosts": self._active_blocked(),
        }

    @gl.public.write
    def set_ttl_checks(self, ttl: u64) -> dict:
        self._require_admin()
        if ttl == 0:
            raise gl.UserError("SafeLink: ttl must be > 0")
        self.ttl_checks = ttl
        return {"ttl_checks": self.ttl_checks}
