# Project Explorer application — DRAFT (do not submit yet)

> Syarif submits this himself via the Portal. Demo URL is live and
> verified (see below). Nothing here has been submitted to the Portal.

## Project name

SafeLink Registry

## One-liner (93 / 100 chars)

Consensus-checked registry of safe, malicious and disputed URLs for wallets, forums and bots.

## Description (1000 / 1000 chars)

SafeLink Registry is a web app for the SafeLink Intelligent Contract on GenLayer Studionet: a shared registry that answers "is this URL safe to open?" for wallets, forums and bots. Anyone can submit a URL; validators independently fetch the page and re-derive the same signals (https, host shape, brand impersonation, password field, off-host form, blocklist), and a safe/malicious/disputed verdict is written only when they agree exactly. Disagreement writes nothing, so a URL is never auto-marked safe. The app is a real client of the contract, not a mock: connect a wallet on Studionet (chain 61999), run an on-chain check and watch the full transaction lifecycle to finalization, look up stored verdicts without a wallet, browse recent entries and stats, and dispute or request a re-check of any entry. Every result links to the Studio explorer. The verdict is a deterministic rule, not a model opinion, so any reviewer can re-derive it from the stored evidence. Studionet testnet; test GEN only.

## How-to steps (for the steward)

1. Open the demo URL and confirm the page shows live registry stats (entries, checks, safe/malicious/disputed counts) read from the contract.
2. In "Check a URL", enter https://example.com/ and click "Look up" (no wallet needed): expect verdict safe.
3. Connect MetaMask or Rabby, let the app add/switch to GenLayer Studionet (chain 61999), enter https://example.edu/ and click "Check on-chain": approve the transaction, wait for finalization, expect verdict safe with a tx hash linking to the Studio explorer. (Use example.edu, not example.net: example.net is already registered and fresh, so checking it would return the cached verdict without a new consensus round.)
4. In "Recent entries", open any entry and click "Re-check" or "Dispute" to confirm those writes work.
5. Confirm the footer states Studionet testnet / test GEN only.

## Expected verification outcome (420 / 500 chars)

The steward sees live stats matching the on-chain registry (3+ entries, safe/malicious counts from get_stats), a read-only lookup returning safe for https://example.com/, and a new on-chain check of https://example.edu/ finalizing with consensus MAJORITY_AGREE, verdict safe, and a Studio explorer link to the transaction. Contract: https://explorer-studio.genlayer.com/address/0x2920A2340F47226490Ac645bDCE64C390Fac40DA

## Links to attach

- Demo URL: https://safe-link-on-gen-layer.vercel.app/ (deployed by Syarif himself on Vercel 13 Nov 2026; verified live by Muse 22:39 WIB — stats, entries, lookup all match the on-chain registry)
- Contract (GenLayer Explorer Contract, Studionet):
  https://explorer-studio.genlayer.com/address/0x2920A2340F47226490Ac645bDCE64C390Fac40DA
- GitHub repository (contract + tests + this app as `app/` when added):
  https://github.com/syariffadilla/SafeLink-On-GenLayer
- Contract file:
  https://github.com/syariffadilla/SafeLink-On-GenLayer/blob/main/contracts/safelink.py

## Verified live evidence (13 Nov 2026)

- `check_url("https://example.net/")` through the app's exact code path
  (`src/lib/safelink.js`): tx
  `0x951e0259d680624915ccad3d57c3f91b43fda3bba57ee63d0a0bebce298c6725`,
  FINALIZED, MAJORITY_AGREE (3 agree, 2 idle), execution SUCCESS, verdict
  **safe** (checked_seq 3). Explorer:
  https://explorer-studio.genlayer.com/tx/0x951e0259d680624915ccad3d57c3f91b43fda3bba57ee63d0a0bebce298c6725
- Registry after that check: 3 entries (example.com safe, example.org
  malicious, example.net safe), check_count 3, disputes 0.
- Reads verified: `get_stats`, `list_entries`, `get_verdict`, `is_safe`,
  `get_brands`, `is_blocked` — all returned live on-chain data matching the
  deployed contract.
