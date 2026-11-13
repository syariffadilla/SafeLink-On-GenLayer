# SafeLink Registry — Project frontend

A real web app for the SafeLink Registry Intelligent Contract on GenLayer
Studionet (chain 61999). It calls the deployed contract — nothing is mocked.

- **Contract:** `0x2920A2340F47226490Ac645bDCE64C390Fac40DA`
  ([Studio explorer](https://explorer-studio.genlayer.com/address/0x2920A2340F47226490Ac645bDCE64C390Fac40DA))
- **Source contract + tests:** `../safelink/` and
  [SafeLink-On-GenLayer](https://github.com/syariffadilla/SafeLink-On-GenLayer)
- **Intelligent Contract:** accepted, 100 Builder pts, 13 Nov 2026.
- **Design:** warm paper / ink, flat verdict colours, serif + grotesque + mono.
  No gradients, no glassmorphism, no marketing hero — the check form and the
  live registry data are the page.

## What it does (contract method in brackets)

- Connect wallet on Studionet, auto add/switch network (`wallet_addEthereumChain`).
- **Check a URL** — on-chain consensus round [`check_url`], full tx lifecycle
  (submitted → finalized), tx hash + explorer link, verdict + all signals.
  Undetermined rounds render as *unchecked*, never as a crash.
- **Look up** — read-only stored verdict [`get_verdict`, `is_safe`], no wallet.
- **Recent entries** [`list_entries`, newest first] and **registry stats**
  [`get_stats`], brands [`get_brands`], blocked hosts.
- **Dispute** [`dispute_url`] and **re-check** [`request_recheck`] on any entry.
- Admin functions (`add/remove_brand`, `block/unblock_host`, `set_ttl_checks`)
  are intentionally NOT in the app: the admin is the Studio deployer account
  (`0x01ED7Ae5A842895C7E05a3CE5587d8DC67a6102F`), not the visitor.

## Run locally

```sh
npm ci
npm run dev        # vite dev server
npm run build      # production build -> dist/
```

## Verify against the live contract (no key needed for reads)

```sh
node scripts/read.mjs
# e2e write path (burner key in /tmp/safelink-e2e-key, Studio faucet, test GEN only):
node scripts/e2e.mjs faucet
node scripts/e2e.mjs check https://example.net/
node scripts/e2e.mjs wait <txhash>
```

Verified 2026-11-13: `check_url("https://example.net/")` →
tx `0x951e0259d680624915ccad3d57c3f91b43fda3bba57ee63d0a0bebce298c6725`,
FINALIZED, MAJORITY_AGREE, verdict **safe** (checked_seq 3).
Registry at that point: 3 entries (example.com safe, example.org malicious,
example.net safe), check_count 3.

## Deploy

Vercel, project `safelink-on-genlayer` (static Vite build, see `vercel.json`).

**Status 2026-11-13 ~21:50 WIB: NOT YET DEPLOYED — Vercel connector is blocked.**
Every project/deployment call (`list_projects`, `get_project`, `create_project`)
fails `403: Not authorized: Trying to access resource under scope
"rifs-projects-9c38a844". You must re-authenticate to this scope.` The stored
connection's default team is `team_vt9ACNubCuTrGmugmwHrE0RX` and no
`authorize_team_access` tool is exposed to fix it from here. The account itself
is fine (`syariffadilla`, hobby plan, connected).

Fix (needs Syarif / parent agent): re-authorize the Vercel connection's access
to that team scope, then retry, in order:

```sh
/opt/hatch/bin/vercel call-tool --name create_project --arguments-json \
  '{"requestBody": {"name": "safelink-on-genlayer", "framework": "vite",
    "buildCommand": "npm run build", "outputDirectory": "dist",
    "installCommand": "npm ci"}}'
# then deploy the prebuilt dist/ (upload each file, then create_deployment
# referencing them by sha), or connect the GitHub repo once app/ is pushed
# and deploy from git instead.
```

The production build is verified locally (see below); deployment is a pure
re-run once auth is fixed — no code changes needed.

## Build smoke test (passed 2026-11-13)

`npm run build` → `dist/` (index 7.99 kB, JS 563 kB / 125 kB gzip, CSS 7.4 kB).
Served with `vite preview`: `/` 200, favicon 200, CSS/JS assets 200, contract
address + Studio explorer URL present in the bundle, 0 gradients in the CSS.

## Testnet only

GenLayer Studionet is a testnet. Test GEN only; nothing here has real value.
Never enter a seed phrase anywhere in this app — it only ever asks the
injected wallet to sign.
