# SafeLink Registry — versions verified

Checked 2026-11-07 ~22:40 WIB (15:40 UTC) by reading the live docs pages
listed below. Nothing here is copied from the 2 Nov 2026 research notes
without re-checking it.

## Decision: target STABLE Studionet, not the v0.6 preview

The SafeLink draft targets stable Studionet (`https://studio.genlayer.com`,
chain ID 61999) and pins the runner hash in the contract header to the
stable hash below. The Consensus v0.6 / Studio v0.123 family is a
release-candidate preview on a separate, temporary chain (Studio-dev,
chain ID 61997, "expect resets"). Mixing the two families is explicitly
warned against in the migration guide, so this draft does not mix them.
Before deploying to Studio-dev / v0.6, re-pin the header to the RC runner
hash from that release's notes — that hash was NOT published inline on any
docs page read for this draft (see "Not verified").

## Verified

| Item | Value | Source (read 2026-11-07) |
|---|---|---|
| GenVM runner, `py-genlayer` | `1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6` | https://sdk.genlayer.com/v0.2.9/impl-spec/appendix/runners-versions.html — listed under `v0.2.1`, `v0.2.4` and `v0.2.5` |
| Same hash, independent corroboration | `1jb45aa8…` = v0.2.5 | genlayer-studio PR #1417 (4 Feb 2026), https://github.com/genlayerlabs/genlayer-studio/pull/1417 — "Replaced `py-genlayer:latest` with fixed version hash `1jb45aa8…` (v0.2.5)" |
| Same hash, also used by GrantFlow | `py-genlayer:1jb45aa8…` (GenVM v0.2.x), deployed Studionet `0x72eEF6Ea426dCaBcD15F0A7B8864900cc0480940` | https://github.com/syariffadilla/GrantFlow-On-GenLayer (README, read 2026-11-07) |
| `genlayer-py` client, PyPI stable | 0.8.1, uploaded 24 Jul 2025 | https://pypi.org/project/genlayer-py/0.8.1/ — **STALE CRAWL, corrected below** |
| `genlayer-py` client, pip index (live, 2026-11-07) | **latest 0.18.0**; genlayer-test 0.29.2 depends on 0.16.3 | `pip index versions genlayer-py` in this VM, 2026-11-07. The PyPI web page crawl showing 0.8.1 as latest is out of date. The docs' "v0.19 RC" is therefore the next line after 0.18.0, which is coherent. |
| Storage structs | classes stored in `TreeMap`/`DynArray` must be annotated `@allow_storage` (imported from `genlayer`) | Proved by the direct run: without it the loader raises `class is not marked for usage within storage, please, annotate it with @allow_storage` (see TEST_LOG.md, run 2). Verified in the extracted SDK: `allow_storage` is exported by `genlayer/__init__.py`. |
| Web response shape | `Response.status: int`, `Response.headers: dict[str, bytes]`, `Response.body: bytes \| None` | Read from the extracted SDK itself: `~/.cache/gltest-direct/extracted/v0.2.16/py-lib-genlayer-std/11rhn002yfajawsz7fai6mykznbxkxs6l91iskj5cm82c92qhy3v/genlayer/gl/nondet/web.py` (`@dataclasses.dataclass class Response`). The docs page shows `response.status_code` — that attribute does not exist anywhere in this SDK's nondet module. The contract uses `.status`. |
| `gl.vm.run_nondet_unsafe` | `run_nondet_unsafe(leader_fn, validator_fn, /)` (positional-only); validator receives `gl.vm.Result` (`Return.calldata`, `UserError.message`, `VMError.message`); validator error counts as Disagree | Same extracted SDK, `genlayer/gl/vm.py`. `UserError` messages are "checked for strict equality by the validator" by default. |
| Stable Studionet | chain ID 61999, https://studio.genlayer.com | https://docs.genlayer.com/developers/consensus-v06-migration and https://docs.genlayer.com/developers/networks |
| Consensus v0.6 preview | Studio v0.123 (rc.5 / rc.6), Studio-dev chain ID 61997, RPC https://studio-dev.genlayer.com/api | https://docs.genlayer.com/developers/consensus-v06-migration, https://docs.genlayer.com/api-references/genlayer-py |
| `genlayer-py` for the v0.6 preview | v0.19 release candidate, must be pinned explicitly (PyPI prerelease tags are not selected by unconstrained installers) | https://docs.genlayer.com/api-references/genlayer-py |
| `genlayer-js` for the v0.6 preview | v2.0 release candidate | https://docs.genlayer.com/api-references/genlayer-js (via search, 2026-11-07) |
| Contract shape | One class extending `gl.Contract`; `@gl.public.view` / `@gl.public.write`; storage as class-level annotations; `list` → `DynArray`, `dict` → `TreeMap`, `int` → sized ints (`u64` etc.); `gl.message.sender_address` is the caller | https://docs.genlayer.com/developers/intelligent-contracts/first-contract |
| Nondet rules | All `gl.nondet.*` calls must be inside a nondet block; storage writes / contract calls / message emission must happen AFTER the nondet block returns, in deterministic code | https://docs.genlayer.com/developers/intelligent-contracts/features/non-determinism |
| Web access | `gl.nondet.web.get(url)` / `.request(url, method, body)` / `.render(url, mode='html'|'screenshot')`; response has `.status_code` and `.body` (bytes); 4xx → `gl.UserError`, 5xx → `gl.UserError` (transient) | https://docs.genlayer.com/developers/intelligent-contracts/features/web-access |
| Equivalence | Leader proposes, validators independently verify; validator must re-run the task / derive from source data — checking only the leader's JSON shape or enum is NOT consensus; `gl.vm.run_nondet_unsafe(leader_fn, validator_fn)` is the recommended custom pattern; validator receives a `gl.vm.Result` (`gl.vm.Return` → `.calldata`, `gl.vm.UserError`, `gl.vm.VMError`); unhandled validator exception counts as Disagree; no consensus → transaction undetermined, no state change | https://docs.genlayer.com/developers/intelligent-contracts/equivalence-principle |

## Correction to the old note

The 2 Nov research note said the hash `1jb45aa8…` was "UNVERIFIED" as
v0.2.5. Re-checking on 2026-11-07: the **v0.2.5** runners page
(`sdk.genlayer.com/v0.2.5/.../runners-versions.html`) lists only
`v0.1.0`, `v0.1.3`, `v0.1.8-runner-hash___` and `vTEST` — and the hash
appears there under `vTEST`, not under a `v0.2.5` key. The **v0.2.9**
runners page lists the same hash under `v0.2.1`, `v0.2.4` **and**
`v0.2.5`, and PR #1417 independently calls it v0.2.5. So the v0.2.5
attribution is now confirmed via the v0.2.9 spec + the PR, not via the
v0.2.5 page alone. The hash itself was never in doubt — only its
version label was.

## Not verified (do not rely on these until checked in Studio)

- **GenVM v0.2.7 runner hash.** The changelog says v0.4.0 "Update genvm
  version to v0.2.7", but no runners-versions page read lists a v0.2.7
  key or hash (the v0.2.9 page tops out at v0.2.5). Do not claim a
  v0.2.7 hash.
- **Exact v0.19 RC tag for `genlayer-py`.** The docs say "install the
  explicit v0.19 release candidate published in the release notes" but
  no exact RC suffix (e.g. `v0.19.0-rc.N`) appears inline on the pages
  read. Same for the v0.6 runner hash.
- **GrantFlow's `genlayer-test` / `genvm-lint` versions in this
  environment.** GrantFlow's README says its first test run downloads
  the GenVM v0.2.16 SDK. Whether that toolchain still installs and runs
  here was tested separately — see `TEST_LOG.md`.
- **Redirect behaviour of `gl.nondet.web.get`.** The docs do not state
  whether it follows redirects or exposes the final URL, so the
  contract deliberately does NOT claim a redirect chain. See
  `CONSENSUS.md` limitations.
- **On-chain clock.** No clock API was verified, so the contract uses a
  monotonic check sequence + `ttl_checks` for freshness instead of
  wall-clock expiry. See `README.md`.
