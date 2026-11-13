// Shared env helpers for the Node scripts.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { generatePrivateKey } from "genlayer-js";

export const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const CONTRACT_ADDRESS =
  process.env.SAFELINK_ADDRESS || "0x2920A2340F47226490Ac645bDCE64C390Fac40DA";

export const json = (v) =>
  JSON.stringify(
    v,
    (_, x) => (typeof x === "bigint" ? x.toString() + "n" : x),
    1,
  );

/** Load a burner key from a file, or generate + save one (testnet only, no real value). */
export function loadOrCreateKeyHex(file) {
  if (fs.existsSync(file)) return fs.readFileSync(file, "utf8").trim();
  const key = generatePrivateKey();
  fs.writeFileSync(file, key, { mode: 0o600 });
  return key;
}
