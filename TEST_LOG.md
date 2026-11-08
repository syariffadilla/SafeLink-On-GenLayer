# SafeLink Registry — test log

Honest record of what was run, what passed, what failed, and what was
NOT run. Dates in WIB (UTC+7). Do not edit the results below to look
better — if a re-run disagrees, append a new entry.

Environment: Python 3.12.3, venv at `safelink/.venv/`
(`python3 -m venv .venv`, `pip install -r requirements.txt`).
System Python is PEP 668-locked, so a venv is required.

## Final state (2026-11-07 ~23:05 WIB)

- Stub suite: **55 passed** — `.venv/bin/python -m pytest tests -q`
- Direct suite (real GenVM engine): **12 passed** —
  `.venv/bin/gltest tests-direct -q`
- Total: **67 passed, 0 failed.**
- `python3 -m py_compile` on all contract + test files: OK.

## Run history (how it got there)

### 1. Stub suite, first run — 37 passed, 18 errors (2026-11-07 ~22:55)

`python -m pytest tests -q` → `37 passed, 18 errors`.
All 18 errors were `NameError: name 'gl' is not defined` at
`class SafeLinkRegistry(gl.Contract)`. Cause: a **stub bug**, not a
contract bug — the fake `genlayer` module did not expose the `gl`
namespace the way the real SDK does (`from genlayer import *` then
`gl.*`). Fix: `fake.gl = fake` in `tests/conftest.py`. The real SDK
exposes `gl` (verified later from the extracted SDK).

### 2. Stub suite, second run — 37 passed, 18 errors (~22:57)

`AttributeError: 'SafeLinkRegistry' object has no attribute 'brands'`
in `__init__`. Cause: **stub gap** — plain Python does not
auto-initialize class-level storage annotations; GenVM does. Fix: the
stub's `Contract` base now initializes storage fields from annotations
via `__init_subclass__` (maps/lists empty, numbers 0). Re-run: **55
passed**.

### 3. Toolchain install (~23:00)

`.venv/bin/pip install genlayer-test` → **genlayer-test 0.29.2**
installed, pulling in **genlayer-py 0.16.3**. `gltest` and `glsim`
binaries present. Note: `pip index versions genlayer-py` shows latest
**0.18.0** — the PyPI web page crawl showing 0.8.1 as latest is stale
(see VERSIONS.md).

### 4. Direct suite, run 1 — 9 failed (~23:02)

`.venv/bin/gltest tests-direct -q` → all 9 failed in
`download_artifacts`: `HTTPError 404` downloading
`https://github.com/genlayerlabs/genvm/releases/download/v0.3.0-rc7/genvm-universal.tar.xz`.
Cause: the loader's "latest" resolution points at **v0.3.0-rc7**,
whose `genvm-universal.tar.xz` asset does not exist at that URL
(the genvm repo was archived 22 Jul 2026). Fix: pin
`sdk_version="v0.2.16"` in the direct tests (the release GrantFlow's
direct tests pinned in Oct 2026). The v0.2.16 tarball downloaded
successfully (~129 MB, cached in `~/.cache/gltest-direct`).

### 5. Direct suite, run 2 — 9 failed (~23:04)

`ImportError: Failed to load contract: ('class is not marked for usage
within storage, please, annotate it with @allow_storage', Entry)`.
Cause: a **real contract bug** — storage structs must carry
`@allow_storage`. This was not in the docs pages read; the loader
found it. Fix: `@allow_storage` on `Entry` (imported from `genlayer`),
plus the same identity decorator in the stub. Re-run stub suite: 55
passed.

### 6. Direct suite, run 3 — 8 failed, 1 passed (~23:06)

Two failures, one real and one test-only:

- **Real:** `AttributeError: 'Response' object has no attribute
  'status_code'` in `leader_fn`. The live docs page shows
  `response.status_code`, but the real SDK's `Response` dataclass
  (`genlayer/gl/nondet/web.py`, v0.2.16) has fields `status`,
  `headers`, `body: bytes | None` — `status_code` appears nowhere in
  that module. Fix: contract now uses `response.status` and handles
  `body=None`; the stub's fake response was updated to match. The
  docs are wrong here; the SDK wins (recorded in VERSIONS.md).
- **Test-only:** `test_deploy_defaults` asserted
  `str(direct_owner) in stats["admin"]`; `direct_owner` is raw bytes,
  while the contract correctly returned the checksummed hex address
  `0xdC18Aa3d…`. Fix: compare via `direct_owner.hex()`. (This failure
  accidentally confirmed the admin address is set correctly.)

### 7. Direct suite, run 4 — 9 passed (~23:07)

After the two fixes above: **9 passed in 0.32s.**

### 8. Direct suite, run 5 — 12 passed (~23:08)

Three tests added (fetch-failure writes nothing, cache served without
a fetch, invalid URL rejected): **12 passed in 0.42s.** Stub suite
re-run at the same time: **55 passed.** Final state above.

## NOT run (open)

- **`genvm-lint` — NOT RUN.** There is no `genvm-lint` package on
  PyPI (`ERROR: No matching distribution found`), no binary in the
  venv, and none in the downloaded GenVM cache. GrantFlow's README
  uses `genvm-lint check` / `typecheck`; that tool was not obtainable
  here. The direct-mode run (real engine loading + executing the
  contract) is the substitute verification, not an equivalent one —
  lint would additionally check method counts and types.
- **Studio live deploy — NOT DONE.** Needs a browser (this draft was
  built without one) and Syarif's Studio session. Steps are in
  README.md. No contract address exists; do not claim one.
- **Consensus v0.6 / Studio-dev (chain 61997) — NOT TESTED.** The
  draft targets stable Studionet only. The v0.6 runner hash and the
  exact v0.19 RC tag were not verifiable from the docs pages read
  (see VERSIONS.md).
- **Real-network consensus** (independent validators, real web) —
  not tested. Direct mode runs leader + validator in-process with
  mocked web responses. A live run against real URLs is the next
  verification step, in Studio.
