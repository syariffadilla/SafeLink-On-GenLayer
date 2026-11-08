# SafeLink Registry — consensus design

How the Equivalence Principle is applied here, what the validator
actually checks, and where v1 deliberately stops. Read alongside
`VERSIONS.md` (which API spellings were verified against the real SDK)
and `TEST_LOG.md` (what the test runs proved and what they did not).

## The pattern

`check_url` uses `gl.vm.run_nondet_unsafe(leader_fn, validator_fn)` —
the custom leader/validator pattern the Equivalence Principle docs call
"the recommended approach for most contracts". This is the same shape
GrantFlow uses for GitHub milestone verification (leader fetches, every
validator re-fetches and compares all evidence fields exactly), applied
to a fetched web page instead of a GitHub API response.

```
check_url(url)                       # deterministic
  normalize(url)                     # pure; invalid -> UserError, no fetch
  fresh non-disputed entry? -> return cached, no nondet
  snapshot brands + blocklist        # BEFORE the nondet block
  gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
    leader_fn():                     # runs on the leader
      response = gl.nondet.web.get(normalized)
      status != 200 -> raise gl.UserError (no verdict, no write)
      body = response.body (bytes, may be None)
      return derive_signals(url, status, body, brands, blocked)
    validator_fn(leaders_res):       # runs independently per validator
      not a gl.vm.Return -> False    # leader failed: disagree, retry
      mine = leader_fn()             # re-fetch + re-derive, from scratch
      compare every COMPARED_SIGNAL_KEYS field exactly
      any difference -> False
  verdict = verdict_from_signals(signals)   # deterministic, pure
  write Entry, bump counters, return entry dict
```

Storage is never read or written inside `leader_fn` / `validator_fn`:
brands and blocklist are snapshotted into locals first, and the entry
is written only after `run_nondet_unsafe` returns, in deterministic
code. This is required by the non-determinism rules (a write inside a
nondet block would land a different value per node before consensus).

## What is compared, and what is not

Compared exactly (`COMPARED_SIGNAL_KEYS` — 10 fields):

`url, host, status_code, is_https, is_ip_literal, is_punycode,
impersonates_brand, has_password_field, off_host_form, blocklisted`

These are all *derived* signals: booleans, a status code, a host
string, a brand name. Two honest nodes fetching the same page at
roughly the same time derive the same values. A validator that only
checked "the leader returned a well-formed dict with a valid verdict
enum" would be leader-output-only validation — the docs explicitly say
that is not consensus. The validator here re-runs the whole fetch and
derivation and compares substance, field by field.

Recorded but NOT compared (`content_len`, `body_sample`): page content
drifts between the leader's fetch and the validators' (timestamps,
ads, A/B variants). Comparing raw content would make consensus fail on
legitimate pages for no security benefit. The verdict never depends on
these two fields — they exist so a human reviewer can see what the
leader saw. This split (compared signals vs. audit observations) is
the one deliberate deviation from GrantFlow's compare-everything
approach, and the reason is documented here, not hidden.

## Why there is no LLM

The verdict is a deterministic rule over derived signals
(`verdict_from_signals`). That is a design choice, not a shortcut:

- The same URL checked twice gives the same verdict. An LLM verdict
  would vary run to run and could only be compared by another LLM
  judgment — weaker, slower, and harder for a reviewer to audit.
- The Portal rubric excludes "thin LLM wrappers" and generic
  "AI decides X" demos. SafeLink's GenLayer value is not the model —
  it is independent re-fetching + exact agreement before a shared
  registry is written.
- If a future version adds LLM classification (e.g. for pages with no
  heuristic signal), it must go through `prompt_comparative` with the
  verdict as a compared field — not as a replacement for the signals.

## Error handling (v1, deliberate)

- **Leader fetch fails (non-200).** The leader raises `gl.UserError`
  ("SafeLink: fetch failed with status N"). The validator sees a
  non-`Return` result and returns `False`. No verdict is written; the
  transaction goes undetermined and can be retried. A URL that cannot
  be fetched stays `unchecked` — v1 never writes a verdict from
  partial data.
- **Leader error agreement is NOT implemented.** The Equivalence
  Principle docs describe matching expected/external errors exactly
  and agreeing when both sides fail transiently. Implementing that
  needs the error payload off the `UserError` result, which was not
  verified against the SDK at build time, so v1 takes the safe
  fallback (disagree → retry with another leader). A permanently
  unreachable URL therefore costs a retry instead of a recorded
  `disputed`. This is a known limitation, listed in the README.
- **Validator throws.** Per the SDK docs, an unhandled validator
  exception counts as `Disagree` — same as returning `False`.
- **Invalid URL.** Rejected deterministically before any fetch
  (`UserError`), so bad input never spends a consensus round.

## Disputes and caching

- `dispute_url` / `request_recheck` set an entry to `disputed` and
  record the reason. Disputed entries are never served from cache:
  the next `check_url` always re-runs consensus, and the dispute
  count + last reason survive the re-check.
- Freshness is `check_count - checked_seq < ttl_checks` (default
  1000 checks). A `safe` verdict therefore ages out after 1000 later
  checks anywhere in the registry — not after a wall-clock duration
  (no clock API was verified). Consumers that need time-based expiry
  should call `request_recheck` or re-`check_url` on their own
  schedule.
- `is_safe` returns true only for a fresh `safe` verdict. Unknown,
  disputed, malicious and stale entries all read as not-safe. There is
  no "probably safe".

## Security notes

- **Never trust the leader.** The validator re-fetches and re-derives;
  the tampered-leader test (`test_validator_rejects_tampered_leader_result`)
  proves a leader that flips signals to `malicious` is rejected even
  though its output is well-formed.
- **Brand list is a heuristic, not ground truth.** Subdomains of a
  real brand (`login.binance.com`) are not impersonation; lookalikes
  (`binance-secure-login.com`, `binance.com.evil.example`) are. A
  phisher who buys a clean-looking domain with no brand string and no
  password field will read `safe` until a human blocklists the host.
  That is why `block_host` exists and why the README lists it as a
  limitation.
- **Admin is a single key** (the deployer). Brands and blocklist are
  admin-only; everything else is permissionless. If the admin key is
  lost, the lists freeze at their last state — checks, reads and
  disputes keep working. Key rotation is future work.
- **No funds in this contract.** There is nothing to escrow, pay out
  or drain. The only admin powers are list curation and TTL.
- **Snapshot-before-nondet.** Brands/blocklist are read into locals
  before `run_nondet_unsafe`; a concurrent list change mid-check
  cannot make the leader and a validator disagree about *which* list
  they used — both sides of one call use the same snapshot because
  both re-run the same `leader_fn` closure over the same locals.
  (A later check uses the newer list, as intended.)

## What the tests prove

- Stub suite (`tests/`, 55 tests): pure logic, state machine, caching,
  disputes, TTL, admin guards, and the consensus flow against a
  stub that emulates leader/validator disagreement.
- Direct suite (`tests-direct/`, 12 tests): the real contract loaded
  by the real GenVM direct engine (SDK v0.2.16) — deploy, mocked-web
  checks, validator agreement, validator disagreement on changed
  pages, tampered-leader rejection, fetch failure, cache behaviour.
- What neither suite proves: a live Studio deployment, real-network
  consensus across independent validators, or behaviour under the
  Consensus v0.6 / Studio v0.123 preview (different runner family).
  See `TEST_LOG.md`.
