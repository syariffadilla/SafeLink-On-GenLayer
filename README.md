# SafeLink Registry

A standalone GenLayer Intelligent Contract: a shared, consensus-checked
registry that answers one question wallets, forums and bots all need —
**is this URL safe to open?**

- Submit a URL → validators independently fetch the page and re-derive
  the same signals → a `safe` / `malicious` / `disputed` verdict is
  written **only when they agree exactly**.
- Disagreement writes nothing. A URL is never auto-marked safe.
- The verdict is a **deterministic rule**, not an LLM opinion — no LLM
  is called anywhere in v1. Any reviewer can re-derive the verdict by
  hand from the stored evidence.
- Entries can be disputed and re-checked; fresh entries are served from
  cache without a new consensus round.

Status: **draft, not submitted, not deployed.** No contract address
exists yet. See `SUBMISSION_DRAFT.md` for the Portal draft and the
checklist before submitting.

## The trust problem

Phishing links are checked today by one person, one tool, or one
model — and a single checker can be wrong, stale, or lying. A wallet
that warns you about a link is trusting whoever produced that warning.
SafeLink moves the warning onto GenLayer consensus: the leader fetches
the page, every validator re-fetches it and re-derives the signals
itself, and the verdict only lands on-chain when they agree. The
evidence (signals + a body sample) is stored with the verdict, so the
decision is auditable after the fact.

## How GenLayer is central

| Step | Contract method | What validators do |
|---|---|---|
| **Check a URL** | `check_url(url)` | The leader fetches the URL with `gl.nondet.web.get` and derives signals (scheme, host shape, brand impersonation, password field, off-host form, blocklist). Every validator re-fetches the same URL and re-derives the signals; the verdict is written only if all compared signal fields match exactly. |
| **Read a verdict** | `get_verdict(url)` / `is_safe(url)` | Pure views — no consensus needed. `is_safe` is true only for a fresh `safe` verdict. |
| **Dispute** | `dispute_url(url, reason)` / `request_recheck(url)` | Anyone can flag an entry as `disputed`. Disputed entries are never served from cache, so the next `check_url` re-runs consensus. |
| **Curate** | `add_brand` / `block_host` (admin only) | The admin maintains the impersonation-brand list and the blocklist. |

No LLM is used: URL safety here is checkable facts (SHAs would be
nice, but pages change — see `CONSENSUS.md` for why only derived
signals are compared). Details: `CONSENSUS.md`.

## State design

Stored in `contracts/safelink.py` (`SafeLinkRegistry`):

| Field | Type | Meaning |
|---|---|---|
| `entries` | `TreeMap[str, Entry]` | Key is the **normalized URL** (not a hash — see below). Value is the full `Entry`. |
| `entry_order` | `DynArray[str]` | Keys in check order; `list_entries` reads newest-first. |
| `brands` / `blocked_hosts` | `DynArray[str]` | Impersonation-brand list and blocklist (admin-curated). |
| `disabled_brands` / `disabled_hosts` | `TreeMap[str, bool]` | Removal tombstones — `DynArray` has no verified remove, so removal sets a flag and snapshots filter it out. |
| `check_count`, `safe/malicious/disputed_count`, `total_disputes` | `u64` | Counters. |
| `ttl_checks` | `u64` | Freshness window in checks (default 1000). See "No wall-clock expiry" below. |

`Entry` (stored value, annotated `@allow_storage` — required by the
real SDK, found by the direct test run):

| Field | Meaning |
|---|---|
| `url`, `verdict` | Normalized URL; `safe` / `malicious` / `disputed`. |
| `status_code`, `host`, `is_https`, `is_ip_literal`, `is_punycode`, `impersonates_brand`, `has_password_field`, `off_host_form`, `blocklisted` | The compared signals — validators must agree on all of them. |
| `content_len`, `body_sample` | Audit observations only — recorded, **never compared** (page content drifts between fetches). |
| `checked_seq` | Global check counter at check time; freshness = `check_count - checked_seq < ttl_checks`. |
| `disputes`, `last_dispute_reason` | Dispute history, preserved across re-checks. |

Why the key is the normalized URL, not a hash: a hash would need
`hashlib` inside the contract, whose availability in GenVM was not
verified. Normalization (`normalize_url` in `contracts/safelink_logic.py`)
lower-cases scheme + host, drops fragments and default ports, and is
fully unit-tested — the normalized string is a safe, human-readable key.

Why freshness is counted in checks, not time: no on-chain clock API
was verified (see `VERSIONS.md`). A wall-clock `expires_at` would have
been invented. `ttl_checks` + `request_recheck` is the honest v1
substitute, and it is listed as a limitation, not hidden.

## Contract API (`contracts/safelink.py`)

| Method | Type | Who | Notes |
|---|---|---|---|
| `check_url(url)` | write, nondet | anyone | Returns the entry dict. Fresh non-disputed entries return `cached: true` with no new consensus round. Non-200 fetch → `UserError`, nothing written. |
| `get_verdict(url)`, `get_entry(url)` | view | anyone | `unchecked` when no entry exists. |
| `is_safe(url)` | view | anyone | True only for a fresh `safe` verdict. |
| `list_entries(offset, limit)` | view | anyone | Newest first, limit capped at 100. |
| `get_stats()` | view | anyone | Counts, TTL, brands, blocklist, admin. |
| `get_brands()`, `is_blocked(host)` | view | anyone | Active (non-disabled) lists. |
| `dispute_url(url, reason)`, `request_recheck(url)` | write | anyone | Sets `disputed`, bumps dispute counters. |
| `add_brand(domain)`, `remove_brand(domain)`, `block_host(host)`, `unblock_host(host)`, `set_ttl_checks(ttl)` | write | admin only | `admin` is the deployer (`gl.message.sender_address` at deploy). |

Verdict rule (`verdict_from_signals`, pure and unit-tested):

- **malicious** — blocklisted host, OR a password field combined with
  plain http, brand impersonation, an IP-literal host, or a form
  posting off-host.
- **disputed** — any single warning on its own (plain http,
  impersonation without a password field, IP-literal / punycode host,
  off-host form).
- **safe** — https, status 200, no warning signal. A password field on
  its own is *not* a warning: legitimate login pages have one.

## Run it

Requires Python 3.12. All commands run from this directory.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # pytest only
.venv/bin/python -m pytest tests -q          # 55 stub tests, no GenVM
```

Direct-mode tests (real GenVM engine, mocked web) need the GenLayer
testing suite, which downloads a ~129 MB GenVM release on first run
(cached in `~/.cache/gltest-direct`):

```bash
.venv/bin/pip install genlayer-test          # 0.29.2 (2026-11-07)
.venv/bin/gltest tests-direct -q             # 12 direct tests
```

`genvm-lint` is **not** available (not on PyPI, no binary found) — see
`TEST_LOG.md`. A Studio deploy + live run is still open (needs a
browser; this draft was built without one):

1. Open https://studio.genlayer.com, create `safelink.py`, paste
   `contracts/safelink.py` (header already pins the stable runner).
2. Deploy to stable Studionet (chain 61999). Record the address.
3. Call `check_url("https://example.com/")` → expect `safe`;
   `check_url` on a known phishing URL → expect `malicious` or
   `disputed`. Record the transaction hashes.
4. Do NOT deploy to Studio-dev / Consensus v0.6 without re-pinning the
   header — see `VERSIONS.md`.

## Versions

Target: **stable Studionet**, GenVM runner `py-genlayer` v0.2.5
(`1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6`). Full
verification record, including two cases where the live docs disagree
with the real SDK (and the SDK won), is in `VERSIONS.md`. Read it
before changing the header.

## Limitations (honest list)

- Heuristic signals only. A phishing page on a compromised legitimate
  domain, or one that matches no signal, will read `safe`. The
  blocklist and brand list are the mitigation, and they are admin
  curated — not a live threat feed.
- No redirect-chain evidence: the docs do not state whether
  `gl.nondet.web.get` follows redirects or exposes the final URL, so
  v1 does not claim it.
- No wall-clock expiry (see state design above).
- Leader fetch failures (non-200, DNS, timeout) produce no verdict —
  the URL stays `unchecked` instead of being marked from partial data.
- Validator error agreement is not implemented in v1: if the leader
  fails, the validator disagrees and the transaction retries with
  another leader. See `CONSENSUS.md`.
- Single admin key for brands/blocklist. A multi-admin or community
  curation model is future work, not v1.

## Repository layout

```
safelink/
  README.md                  this file
  CONSENSUS.md               leader/validator design + security notes
  VERSIONS.md                SDK/runner versions, verified 2026-11-07
  TEST_LOG.md                honest test log, incl. failures found
  SUBMISSION_DRAFT.md        Portal submission draft (DO NOT SUBMIT yet)
  requirements.txt           pytest (stub tests)
  pytest.ini
  contracts/
    safelink.py              the contract (self-contained, deployable)
    safelink_logic.py        pure logic, stdlib only (unit-tested)
  tests/                     stub tests: 55 tests, no GenVM needed
    conftest.py              fake genlayer module (stub semantics documented)
    test_logic.py            normalize / signals / verdict matrix
    test_contract.py         state machine + consensus flow via stub
    test_contract_sync.py    guards the logic/contract duplication
  tests-direct/              real GenVM direct-mode tests: 12 tests
    test_safelink_direct.py  deploy + mocked-web consensus via gltest
```

Layout mirrors GrantFlow
(https://github.com/syariffadilla/GrantFlow-On-GenLayer — `contracts/`,
`tests/direct/`, `README.md`, `CONSENSUS.md`) for the repo shape only;
no GrantFlow contract logic was copied.
