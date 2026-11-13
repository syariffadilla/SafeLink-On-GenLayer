// SafeLink Registry — browser app.
// Reads work without a wallet. Writes (check / dispute / re-check) need an
// injected wallet (MetaMask / Rabby) switched to GenLayer Studionet, chain 61999.
// Testnet only: test GEN, no real value.
import { CONTRACT_ADDRESS, EXPLORER } from "./config.js";
import {
  api, readClient, walletClient, summarizeReceipt,
  txUrl, addressUrl, balanceOf,
} from "./lib/safelink.js";

const $ = (id) => document.getElementById(id);
const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const shortAddr = (a) => (a ? `${a.slice(0, 6)}…${a.slice(-4)}` : "");
const nowTime = () => new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

const rc = readClient();
let wallet = null; // { client, address } once connected
let entriesCache = [];

const VERDICT_CLASS = { safe: "safe", malicious: "malicious", disputed: "disputed", unchecked: "unchecked" };
const badge = (v) => `<span class="badge ${VERDICT_CLASS[v] || "unchecked"}">${esc(v || "unchecked")}</span>`;
const boolWord = (b) => (b ? "yes" : "no");

// ------------------------------------------------------------------ data

async function loadStats() {
  try {
    const s = await api.stats(rc, CONTRACT_ADDRESS);
    for (const [k, v] of Object.entries(s)) {
      const el = document.querySelector(`[data-stat="${k}"]`);
      if (el) el.textContent = String(v);
    }
    $("statsNote").textContent =
      `TTL ${s.ttl_checks} checks · admin ${shortAddr(s.admin)} (deployer account; admin actions are not in this app) · updated ${nowTime()}`;
    renderBrands(s.brands, s.blocked_hosts);
  } catch (e) {
    $("statsNote").textContent = `Could not read stats: ${e.message || e}. The Studio RPC is sometimes slow — try Refresh.`;
  }
}

function renderBrands(brands, blocked) {
  $("brandsList").innerHTML =
    (brands || []).map((b) => `<li>${esc(b)}</li>`).join("") || "<li>None</li>";
  $("blockedList").innerHTML =
    (blocked || []).map((b) => `<li>${esc(b)}</li>`).join("") || "<li>None</li>";
}

async function loadEntries() {
  const note = $("entriesNote");
  try {
    const list = await api.entries(rc, CONTRACT_ADDRESS, 0, 20);
    entriesCache = list.entries || [];
    renderEntries();
    note.textContent = `${list.total} entr${list.total === 1 ? "y" : "ies"} in the registry · updated ${nowTime()}`;
  } catch (e) {
    note.textContent = `Could not read entries: ${e.message || e}. The Studio RPC is sometimes slow — try Refresh.`;
  }
}

function renderEntries() {
  const table = $("entriesTable");
  const body = $("entriesBody");
  if (!entriesCache.length) {
    table.hidden = true;
    $("entriesNote").textContent = "No entries yet. Run the first check above.";
    return;
  }
  table.hidden = false;
  body.innerHTML = entriesCache
    .map(
      (e) => `<tr>
        <td>${badge(e.verdict)}</td>
        <td class="url">${esc(e.url)}</td>
        <td class="mono">${esc(e.host)}</td>
        <td class="num">${esc(e.status_code)}</td>
        <td class="num">${esc(e.disputes)}${e.last_dispute_reason ? ` — ${esc(e.last_dispute_reason)}` : ""}</td>
        <td class="row-actions">
          <button class="link-btn" data-act="lookup" data-url="${esc(e.url)}">View</button>
          <button class="link-btn" data-act="recheck" data-url="${esc(e.url)}">Re-check</button>
          <button class="link-btn" data-act="dispute" data-url="${esc(e.url)}">Dispute</button>
        </td>
      </tr>
      <tr class="detail" data-detail-for="${esc(e.url)}" hidden>
        <td colspan="6"><div class="dispute-form">
          <input type="text" placeholder="Reason for disputing this verdict (e.g. page has changed)" maxlength="200" />
          <button class="btn btn-ink btn-small" data-act="dispute-confirm" data-url="${esc(e.url)}">Submit dispute</button>
        </div></td>
      </tr>`,
    )
    .join("");
}

// ------------------------------------------------------------------ receipt

function signalRows(e) {
  const rows = [
    ["URL", e.url],
    ["Verdict", null], // badge row, handled by caller
    ["Fresh", e.fresh ? `yes — checked at sequence ${e.checked_seq}` : "no — stale, re-check to refresh"],
    ["Cached", boolWord(e.cached)],
    ["Status code", e.status_code],
    ["Host", e.host],
    ["HTTPS", boolWord(e.is_https)],
    ["IP-literal host", boolWord(e.is_ip_literal)],
    ["Punycode host", boolWord(e.is_punycode)],
    ["Impersonates brand", e.impersonates_brand || "—"],
    ["Password field", boolWord(e.has_password_field)],
    ["Off-host form", boolWord(e.off_host_form)],
    ["Blocklisted", boolWord(e.blocklisted)],
    ["Content length", e.content_len],
    ["Disputes", `${e.disputes}${e.last_dispute_reason ? ` — last: ${e.last_dispute_reason}` : ""}`],
    ["Checked seq", e.checked_seq],
  ];
  return rows;
}

function renderReceipt({ entry, source, tx, consensus, votes, note }) {
  const box = $("result");
  const v = entry?.verdict || "unchecked";
  const agree = votes ? Object.values(votes).filter((x) => x === "agree").length : null;
  const total = votes ? Object.keys(votes).length : null;
  box.hidden = false;
  box.innerHTML = `
    <div class="receipt-head">
      <h3>${v === "unchecked" ? "Unchecked" : `Verdict: ${esc(v)}`}</h3>
      ${badge(v)}
    </div>
    <dl>
      ${signalRows(entry || {})
        .filter(([, val]) => val !== null)
        .map(([k, val]) => `<div class="row"><dt>${esc(k)}</dt><dd>${esc(val)}</dd></div>`)
        .join("")}
      ${entry?.body_sample ? `<div class="row"><dt>Page sample</dt><dd class="body-sample">${esc(entry.body_sample)}</dd></div>` : ""}
      <div class="row"><dt>Source</dt><dd class="plain">${esc(source)}</dd></div>
      ${tx ? `<div class="row"><dt>Transaction</dt><dd><a href="${esc(txUrl(tx))}" target="_blank" rel="noopener">${esc(tx)}</a></dd></div>` : ""}
      ${consensus ? `<div class="row"><dt>Consensus</dt><dd>${esc(consensus)}${agree !== null ? ` — ${agree} of ${total} validators agreed` : ""}</dd></div>` : ""}
      ${note ? `<div class="row"><dt>Note</dt><dd class="plain">${esc(note)}</dd></div>` : ""}
    </dl>`;
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderUnchecked({ url, tx, consensus, note }) {
  const box = $("result");
  box.hidden = false;
  box.innerHTML = `
    <div class="receipt-head"><h3>Unchecked</h3>${badge("unchecked")}</div>
    <dl>
      <div class="row"><dt>URL</dt><dd>${esc(url)}</dd></div>
      <div class="row"><dt>Verdict</dt><dd>unchecked — no verdict was written</dd></div>
      ${tx ? `<div class="row"><dt>Transaction</dt><dd><a href="${esc(txUrl(tx))}" target="_blank" rel="noopener">${esc(tx)}</a></dd></div>` : ""}
      ${consensus ? `<div class="row"><dt>Consensus</dt><dd>${esc(consensus)}</dd></div>` : ""}
      <div class="row"><dt>Note</dt><dd class="plain">${esc(
        note ||
          "Validators could not agree — the page could not be fetched with a usable HTTP 200 response, so by design nothing was written. This is not an error in the registry.",
      )}</dd></div>
    </dl>`;
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function setTxStatus(html) {
  const el = $("txStatus");
  if (!html) {
    el.hidden = true;
    el.innerHTML = "";
    return;
  }
  el.hidden = false;
  el.innerHTML = html;
}

function setBusy(busy) {
  $("checkBtn").disabled = busy;
  $("lookupBtn").disabled = busy;
  $("connectBtn").disabled = busy;
}

// ------------------------------------------------------------------ actions

function validUrl(raw) {
  const u = String(raw || "").trim();
  if (!/^https?:\/\//i.test(u)) return null;
  if (/\s/.test(u) || u.length > 2048) return null;
  return u;
}

async function doLookup(url) {
  setBusy(true);
  setTxStatus("");
  $("result").hidden = true;
  try {
    const [entry, safe] = await Promise.all([
      api.verdict(rc, CONTRACT_ADDRESS, url),
      api.isSafe(rc, CONTRACT_ADDRESS, url),
    ]);
    if (entry.verdict === "unchecked") {
      renderUnchecked({ url, note: "No stored verdict for this URL yet. Run a check on-chain to ask the validators." });
    } else {
      renderReceipt({
        entry,
        source: `Read-only lookup (get_verdict + is_safe) — no transaction. is_safe: ${safe}.`,
      });
    }
  } catch (e) {
    renderUnchecked({ url, note: `Lookup failed: ${e.message || e}` });
  } finally {
    setBusy(false);
  }
}

async function doCheck(url) {
  if (!wallet) {
    setTxStatus(`<span class="stage">Wallet needed.</span> Connect a wallet on Studionet first — the check is an on-chain write.`);
    return;
  }
  setBusy(true);
  setTxStatus(`<span class="stage">Preparing check…</span>`);
  $("result").hidden = true;
  try {
    const summary = await api.checkUrl(wallet.client, CONTRACT_ADDRESS, url, (stage, info) => {
      if (stage === "sent") {
        setTxStatus(
          `<span class="stage">Submitted — waiting for consensus…</span><br/>` +
            `<span class="mono">tx <a href="${esc(txUrl(info.hash))}" target="_blank" rel="noopener">${esc(info.hash)}</a></span><br/>` +
            `<span class="fineprint">Validators are fetching the page now. This usually takes about a minute.</span>`,
        );
      }
    });
    if (summary.undetermined) {
      setTxStatus(
        `<span class="stage">Finalized — undetermined.</span><br/>` +
          `<span class="mono">tx <a href="${esc(txUrl(summary.hash))}" target="_blank" rel="noopener">${esc(summary.hash)}</a></span>`,
      );
      renderUnchecked({ url, tx: summary.hash, consensus: summary.consensus });
    } else if (summary.ok) {
      const entry = summary.returned && typeof summary.returned === "object"
        ? summary.returned
        : await api.entry(rc, CONTRACT_ADDRESS, url);
      setTxStatus(
        `<span class="stage">Finalized — ${esc(summary.consensus || "accepted")}.</span><br/>` +
          `<span class="mono">tx <a href="${esc(txUrl(summary.hash))}" target="_blank" rel="noopener">${esc(summary.hash)}</a></span>`,
      );
      renderReceipt({
        entry,
        source: `On-chain check (check_url)${entry.cached ? " — fresh stored entry returned, no new consensus round" : " — new consensus round"}.`,
        tx: summary.hash,
        consensus: summary.consensus,
        votes: summary.votes,
      });
    } else {
      setTxStatus(`<span class="stage">Finalized with an error.</span>`);
      renderUnchecked({ url, tx: summary.hash, consensus: summary.consensus, note: `Execution failed: ${summary.error || "unknown error"}` });
    }
  } catch (e) {
    setTxStatus(`<span class="stage">Check failed.</span> ${esc(e.message || e)}`);
  } finally {
    setBusy(false);
    await refreshAll();
  }
}

async function doRecheck(url) {
  if (!wallet) {
    setTxStatus(`<span class="stage">Wallet needed.</span> Connect a wallet on Studionet first.`);
    return;
  }
  setBusy(true);
  try {
    const summary = await api.requestRecheck(wallet.client, CONTRACT_ADDRESS, url, (stage, info) => {
      if (stage === "sent") setTxStatus(`<span class="stage">Re-check submitted…</span> <span class="mono"><a href="${esc(txUrl(info.hash))}" target="_blank" rel="noopener">${esc(info.hash)}</a></span>`);
    });
    setTxStatus(
      `<span class="stage">Re-check ${summary.undetermined ? "finalized — undetermined" : "finalized — " + esc(summary.consensus || "")}.</span> ` +
        `<span class="mono"><a href="${esc(txUrl(summary.hash))}" target="_blank" rel="noopener">${esc(summary.hash)}</a></span> The entry is now disputed and the next check re-runs consensus.`,
    );
  } catch (e) {
    setTxStatus(`<span class="stage">Re-check failed.</span> ${esc(e.message || e)}`);
  } finally {
    setBusy(false);
    await refreshAll();
  }
}

async function doDispute(url, reason) {
  if (!wallet) {
    setTxStatus(`<span class="stage">Wallet needed.</span> Connect a wallet on Studionet first.`);
    return;
  }
  setBusy(true);
  try {
    const summary = await api.disputeUrl(wallet.client, CONTRACT_ADDRESS, url, reason, (stage, info) => {
      if (stage === "sent") setTxStatus(`<span class="stage">Dispute submitted…</span> <span class="mono"><a href="${esc(txUrl(info.hash))}" target="_blank" rel="noopener">${esc(info.hash)}</a></span>`);
    });
    setTxStatus(
      `<span class="stage">Dispute finalized — ${esc(summary.consensus || "")}.</span> ` +
        `<span class="mono"><a href="${esc(txUrl(summary.hash))}" target="_blank" rel="noopener">${esc(summary.hash)}</a></span> The entry is now disputed.`,
    );
  } catch (e) {
    setTxStatus(`<span class="stage">Dispute failed.</span> ${esc(e.message || e)}`);
  } finally {
    setBusy(false);
    await refreshAll();
  }
}

// ------------------------------------------------------------------ wallet

async function connectWallet() {
  if (!window.ethereum) {
    setTxStatus(`<span class="stage">No wallet found.</span> Install MetaMask or Rabby, then reload this page. Nothing here will ever ask for a seed phrase.`);
    return;
  }
  setBusy(true);
  try {
    wallet = await walletClient(window.ethereum);
    const bal = await balanceOf(rc, wallet.address).catch(() => null);
    $("connectBtn").textContent = `Connected · ${shortAddr(wallet.address)}`;
    $("walletStatus").innerHTML =
      `Connected as <span class="mono">${esc(wallet.address)}</span> · Studionet 61999` +
      (bal !== null ? ` · balance ${esc((Number(bal) / 1e18).toFixed(4))} GEN (test)` : "") +
      ` · <a href="${esc(addressUrl(wallet.address))}" target="_blank" rel="noopener">explorer</a>`;
    setTxStatus("");
  } catch (e) {
    setTxStatus(`<span class="stage">Could not connect.</span> ${esc(e.message || e)}`);
  } finally {
    setBusy(false);
  }
}

// ------------------------------------------------------------------ wiring

async function refreshAll() {
  await Promise.allSettled([loadStats(), loadEntries()]);
}

$("checkForm").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const url = validUrl($("urlInput").value);
  if (!url) {
    setTxStatus(`<span class="stage">Invalid URL.</span> Enter a full http(s) URL, e.g. https://example.com/`);
    return;
  }
  doCheck(url);
});

$("lookupBtn").addEventListener("click", () => {
  const url = validUrl($("urlInput").value);
  if (!url) {
    setTxStatus(`<span class="stage">Invalid URL.</span> Enter a full http(s) URL, e.g. https://example.com/`);
    return;
  }
  doLookup(url);
});

$("refreshBtn").addEventListener("click", refreshAll);
$("connectBtn").addEventListener("click", connectWallet);

$("entriesBody").addEventListener("click", (ev) => {
  const btn = ev.target.closest("[data-act]");
  if (!btn) return;
  const url = btn.dataset.url;
  const act = btn.dataset.act;
  if (act === "lookup") {
    $("urlInput").value = url;
    doLookup(url);
  } else if (act === "recheck") {
    doRecheck(url);
  } else if (act === "dispute") {
    const row = document.querySelector(`tr[data-detail-for="${CSS.escape(url)}"]`);
    if (row) row.hidden = !row.hidden;
  } else if (act === "dispute-confirm") {
    const input = btn.closest(".dispute-form").querySelector("input");
    const reason = input.value.trim();
    if (!reason) {
      input.focus();
      return;
    }
    doDispute(url, reason.slice(0, 200));
  }
});

if (window.ethereum) {
  window.ethereum.on?.("accountsChanged", () => {
    wallet = null;
    $("connectBtn").textContent = "Connect wallet";
    $("walletStatus").textContent = "Read-only — no wallet connected";
  });
  window.ethereum.on?.("chainChanged", () => {
    wallet = null;
    $("connectBtn").textContent = "Connect wallet";
    $("walletStatus").textContent = "Read-only — no wallet connected";
  });
}

refreshAll();
