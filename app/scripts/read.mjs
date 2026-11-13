// Read-only: print the live state of the deployed SafeLink contract (no key needed).
//   node scripts/read.mjs [0xContract]
import { CONTRACT_ADDRESS as DEFAULT_ADDRESS, json } from "./_env.mjs";
import { api, readClient } from "../src/lib/safelink.js";

const A = process.argv[2] || DEFAULT_ADDRESS;
const c = readClient();
console.log("contract", A);
console.log("stats", json(await api.stats(c, A)));
const list = await api.entries(c, A, 0, 20);
console.log("list_entries total", list.total, "returned", list.entries.length);
for (const e of list.entries) {
  console.log("entry", json(e));
}
for (const url of ["https://example.com/", "https://example.org/"]) {
  console.log("get_verdict", url, json(await api.verdict(c, A, url)));
  console.log("is_safe", url, json(await api.isSafe(c, A, url)));
}
console.log("brands", json(await api.brands(c, A)));
console.log("is_blocked example.org", json(await api.isBlocked(c, A, "example.org")));
console.log("is_blocked example.com", json(await api.isBlocked(c, A, "example.com")));
