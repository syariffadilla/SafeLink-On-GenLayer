# Why the two phishing lookalikes ended UNDETERMINED — investigation 2026-11-08 13:15 WIB

## Studio result being explained

- `check_url("https://metamask-login-secure.com/login")` → FINALIZED but UNDETERMINED after 3 leader rotations, `get_verdict` = `unchecked`.
- `check_url("https://metamask.com/login")` → same, UNDETERMINED, `unchecked`.
- Control: `check_url("https://example.com/")` → `safe`, consensus reached.

## Root cause (verified by re-fetching the same URLs twice from this VM, 2026-11-08 ~13:15 WIB)

Both test URLs were bad test choices — they return no usable 200 page at all:

1. `https://metamask-login-secure.com/login` — **RemoteDisconnected, twice.** The server closes the connection without any HTTP response. No status code exists to derive signals from.
2. `https://metamask.com/login` — **HTTP 404, twice.** The path does not exist on the real metamask.com.

In the contract, `leader_fn` raises `gl.UserError` when `response.status != 200`, and `validator_fn` returns `False` for any non-`Return` leader result. So a failed fetch can never reach consensus — by design. This is **not** a signal disagreement and **not** a contract bug: the contract refused to write a verdict from partial data, exactly as documented in CONSENSUS.md ("a URL that cannot be fetched stays `unchecked`").

## Clean way to demonstrate `malicious` (verified locally, not yet run in Studio)

Use the admin blocklist path on a host that serves a stable 200 page, so every signal is identical across validators:

- `https://example.org/` — status 200, 577 bytes, **identical on both fetches**; with `blocklisted=True` the local logic returns `malicious`.
- `https://httpbin.org/` — status 200, 8141 bytes, **identical on both fetches**; with `blocklisted=True` also `malicious`.
- `https://neverssl.com/` — RemoteDisconnected twice from this VM too; do NOT use it as a demo host.

Proposed Studio run (needs Syarif's approval — it mutates the deployed Studio registry): as admin, `block_host("example.org")`, then `check_url("https://example.org/")` → expect `malicious`, consensus reached. This demonstrates the `malicious` branch end-to-end without depending on a live phishing site staying up.

## What this does NOT prove

- A live phishing page (impersonation + password field) producing `malicious` via heuristics alone was still not demonstrated — the blocklist path proves the verdict machinery, not the heuristic detection of a real phishing page.
- Real-network consensus across independent validators was still not tested; Studio's local consensus is the only live run so far.
