// Live end-to-end run against the deployed SafeLink contract on GenLayer
// Studionet, using the same library as the web app (src/lib/safelink.js).
// Each step is a separate invocation so long consensus rounds don't block:
//
//   node scripts/e2e.mjs faucet                 # Studio faucet for the burner (test GEN)
//   node scripts/e2e.mjs check <url>           # check_url via the burner key (default: https://example.net/)
//   node scripts/e2e.mjs wait <txhash>          # wait until FINALIZED and print the outcome
//   node scripts/e2e.mjs status <txhash>        # print the current status of a tx
//   node scripts/e2e.mjs dispute <url> <reason> # dispute_url via the burner key
//   node scripts/e2e.mjs recheck <url>          # request_recheck via the burner key
//
// Results are appended to ../safelink-e2e-log.json (outside the repo).
// The burner key lives in /tmp/safelink-e2e-key (0600); Studionet test GEN only.
import fs from "node:fs";
import path from "node:path";
import { TransactionStatus } from "genlayer-js/types";
import { REPO_ROOT, CONTRACT_ADDRESS, loadOrCreateKeyHex, json } from "./_env.mjs";
import { api, keyClient, readClient, studioFaucet, summarizeReceipt } from "../src/lib/safelink.js";

const ADDRESS = CONTRACT_ADDRESS;
const LOG = path.join(REPO_ROOT, "..", "safelink-e2e-log.json");
const KEY_FILE = "/tmp/safelink-e2e-key";
const burner = keyClient(loadOrCreateKeyHex(KEY_FILE));
const rc = readClient();

function log(step, data) {
  const all = fs.existsSync(LOG) ? JSON.parse(fs.readFileSync(LOG, "utf8")) : [];
  all.push({ at: new Date().toISOString(), contract: ADDRESS, step, data: JSON.parse(json(data)) });
  fs.writeFileSync(LOG, JSON.stringify(all, null, 1));
  console.log(step, json(data));
}

const cb = (stage, info) => console.log(" ", stage, info.hash ?? "", info.status ?? "", info.consensus ?? "");
const [step, a1, a2] = process.argv.slice(2);

if (step === "faucet") {
  const r = await studioFaucet(rc, burner.address, 5);
  log("faucet", { tx: r, address: burner.address });
} else if (step === "check") {
  const url = a1 || "https://example.net/";
  const r = await api.checkUrl(burner.client, ADDRESS, url, cb);
  log("check_url", { url, caller: burner.address, ...r });
} else if (step === "wait") {
  const receipt = await rc.waitForTransactionReceipt({ hash: a1, status: TransactionStatus.FINALIZED, interval: 5000, retries: 120 });
  log("tx_outcome", summarizeReceipt(receipt));
} else if (step === "status") {
  const tx = await rc.getTransaction({ hash: a1 });
  log("tx_status", { hash: a1, status: tx.statusName ?? tx.status_name ?? tx.status, result: tx.resultName ?? tx.result_name ?? null });
} else if (step === "dispute") {
  const r = await api.disputeUrl(burner.client, ADDRESS, a1, a2 || "Disputed from the SafeLink e2e script (Studionet test account).", cb);
  log("dispute_url", { url: a1, caller: burner.address, ...r });
} else if (step === "recheck") {
  const r = await api.requestRecheck(burner.client, ADDRESS, a1, cb);
  log("request_recheck", { url: a1, caller: burner.address, ...r });
} else {
  console.log("burner", burner.address);
  console.log("unknown step; see header");
}
