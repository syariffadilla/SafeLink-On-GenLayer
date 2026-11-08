# Portal submission DRAFT — SafeLink Registry

> **DO NOT SUBMIT YET.** This is a draft for Syarif to review. Nothing
> has been submitted to the Portal, no GitHub repo has been created, no
> contract has been deployed, nothing has been signed or spent. The
> checklist at the bottom must be cleared first.

## Submission fields

- **Category:** Builder → Intelligent Contracts
- **Title:** SafeLink Registry — consensus-checked URL safety registry
- **Week:** week of 7 Nov 2026 — screenshot 7 Nov shows **0 of 2 slots
  used**, resets Monday 00:00 UTC (07:00 WIB). This draft uses 1 slot.
- **Description** (draft text below; 771 characters — kept short
  because the form's exact limit was not verified):

> SafeLink Registry is a standalone GenLayer Intelligent Contract that
> answers one question wallets, forums and bots all need: is this URL
> safe to open? Any account can submit a URL; validators independently
> fetch the page and re-derive the same signals (https, host shape,
> brand impersonation, password field, off-host form, admin blocklist),
> and a safe/malicious/disputed verdict is written only when they agree
> exactly. Disagreement writes nothing — a URL is never auto-marked
> safe. The verdict is a deterministic rule, not an LLM opinion, so any
> reviewer can re-derive it from the stored evidence. Entries can be
> disputed and re-checked; fresh entries are served from cache.
> Includes 67 passing tests (55 stub + 12 real GenVM direct-mode) and
> full version verification.

## Evidence to attach

- GitHub repo URL: **NOT CREATED YET.** Create a public repo from
  the `safelink/` folder (see checklist) and paste its URL here.
  Suggested name: `SafeLink-On-GenLayer` (mirrors
  `GrantFlow-On-GenLayer`).
- Files reviewers should read, in order: `README.md`, `CONSENSUS.md`,
  `VERSIONS.md`, `TEST_LOG.md`, then `contracts/safelink.py`.
- Contract file for Studio: `contracts/safelink.py` (header already
  pins the stable runner `py-genlayer:1jb45aa8…` v0.2.5).
- Deployed address: **0x2920A2340F47226490Ac645bDCE64C390Fac40DA** — Studio stable Studionet chain 61999, deployed 2026-11-08 13:05-13:14 WIB, deploy tx 0xb2b11b75c91e487daa3a8fef25759fccb4cc1b1e26b775fc2547b586acd019c0 (FINALIZED, consensus reached, "Contract deployed"). Deploying account shown in Studio: 0x01ED7Ae5A842895C7E05a3CE5587d8DC67a6102F (Studio local account, 0 GEN shown).
- Live-run: check_url("https://example.com/") → `safe`, tx 0x693126ea0173567c52b453e52ad0a00bc916f4f6ed6bdb686cc36158a9b72467 (FINALIZED, consensus reached). Phishing-pattern URLs did NOT produce a `malicious` verdict: check_url("https://metamask-login-secure.com/login") tx 0x61b47e6cad031aeeae8719d7666b966fd0261fd441fa22cdd6967d26024d6135 and check_url("https://metamask.com/login") tx 0xb27db3870989cec1e1d5e99b29f9156b3ea4d2346da188fe030f992eaaffa3d1 both FINALIZED but UNDETERMINED after 3 leader rotations ("Failed to reach consensus"), get_verdict `unchecked` — disputed branch per design, no verdict written. Investigation (UNDETERMINED_INVESTIGATION.md): both URLs return no usable 200 page (one closes the connection, the other is HTTP 404) — not a contract bug.
- Malicious demo 2026-11-08 13:18-13:21 WIB (approved by Syarif): block_host("example.org") tx 0x74ad4973e29c4ab655376a29ad4c08b9462f5e66f1e92f1d38593e761f3b1615 FINALIZED, consensus reached, is_blocked true; then check_url("https://example.org/") tx 0xce30e5425efcb3d933d1d47b249e899de11e70c3504cb1764c35d56e8add8c4c FINALIZED, consensus reached, get_verdict `malicious` (blocklisted true, status 200, content_len 577, fresh true). Malicious branch now demonstrated end-to-end via the blocklist path.

## What this is NOT (say it plainly in the submission if asked)

- Not a full app — no frontend. A frontend would belong under
  Projects, not Intelligent Contracts.
- Not an update to GrantFlow / PadiGuard / MilestoneGrant — a new
  standalone primitive. No GrantFlow logic was copied.
- Not an LLM product — no LLM is called. The GenLayer value is
  independent re-fetching + exact agreement before a shared registry
  is written.

## Checklist before submitting

- [ ] Syarif reviews this draft and the README (especially the
      Limitations section — the honest limits are part of the pitch).
- [ ] Create the public GitHub repo from `safelink/` (exclude
      `.venv/`, `artifacts/`, `__pycache__/` — `.gitignore` is
      included) and paste the URL above.
- [ ] Deploy `contracts/safelink.py` in GenLayer Studio to stable
      Studionet; record address + deploy tx hash.
- [ ] Live-run in Studio: `check_url("https://example.com/")` →
      expect `safe`; a phishing-pattern URL → expect `malicious` or
      `disputed`. Record the tx hashes in the submission evidence.
- [ ] Re-verify the runner pin against the docs on deploy day — if
      Studio has moved to the Consensus v0.6 family by then, re-pin
      per `VERSIONS.md` and re-run the direct tests.
- [ ] Submit via https://portal.genlayer.foundation/submit-contribution
      (Builder → Intelligent Contracts), 1 of the 2 weekly slots.
- [ ] Do NOT claim a point score anywhere in the submission. GrantFlow
      and PadiGuard each received 380 points in Season 1; Season 2
      points are awarded more selectively and no score is promised.
