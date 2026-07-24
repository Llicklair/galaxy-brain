#!/usr/bin/env node
// galaxy-brain — typed, file-based loop memory (ARCHITECTURE rule 9 / v1.0 gate; research H5).
//
// The loop already keeps prose state (state.md, coverage.md, inbox, ledger) OUTSIDE the repo.
// Prose has a cost: every pass re-reads it to "subtract the ledger". This turns that state into
// TYPED observations the loop appends once and QUERIES by relevance — so pass N+1 recalls what
// pass N learned without re-reading everything, and never re-triages a finding it already judged.
//
// NO vector memory (SCOPE anti-goal, research H5): plain JSONL + lexical/tag scoring. The store
// lives outside the repo, one file per repo, exactly like the existing loop state.
//
// Record shape (one JSON object per line):
//   { id, ts, type, key, title, tags:[], severity?, verdict?, ref?, body? }
//   type ∈ finding | decision | verdict   (the three claude-mem-style observation kinds)
//   key  = stable dedup key (e.g. "file:line:family") so the same finding is never stored twice.
//
// Usage:
//   loop-memory.js append --store <path> --type finding --key <k> --title <t> [--tags a,b] [--severity high] [--verdict real] [--ref url] [--body "..."]
//   loop-memory.js query  --store <path> [--type finding] [--tags a,b] [--text "..."] [--limit 10] [--json]
//   loop-memory.js seen   --store <path> --key <k>            # exit 0 if present, 1 if new
//   loop-memory.js stats  --store <path> [--json]
//
// ts is injected by the caller via --ts (epoch ms) when determinism matters; otherwise omitted.
// This script never calls Date.now() itself so it stays pure/testable — the loop stamps time.

const fs = require("node:fs");
const path = require("node:path");

function arg(name, fallback = undefined) {
  const i = process.argv.indexOf(name);
  return i >= 0 && i + 1 < process.argv.length ? process.argv[i + 1] : fallback;
}
const hasFlag = (n) => process.argv.includes(n);
const list = (s) => (s ? s.split(",").map((x) => x.trim()).filter(Boolean) : []);

function die(msg) {
  process.stderr.write(msg + "\n");
  process.exit(2);
}

function readAll(store) {
  if (!store) die("--store <path> is required");
  if (!fs.existsSync(store)) return [];
  const out = [];
  for (const line of fs.readFileSync(store, "utf8").split("\n")) {
    const s = line.trim();
    if (!s) continue;
    try {
      out.push(JSON.parse(s));
    } catch {
      // A corrupt line must never crash recall — skip it, keep the rest.
    }
  }
  return out;
}

function appendRecord(store, rec) {
  fs.mkdirSync(path.dirname(store), { recursive: true });
  fs.appendFileSync(store, JSON.stringify(rec) + "\n", "utf8");
}

const TYPES = new Set(["finding", "decision", "verdict"]);

function cmdAppend(store) {
  const type = arg("--type");
  const key = arg("--key");
  const title = arg("--title");
  if (!TYPES.has(type)) die(`--type must be one of finding|decision|verdict (got ${type})`);
  if (!key) die("--key <stable-dedup-key> is required");
  if (!title) die("--title <text> is required");

  // Idempotent by key: a finding already stored is updated in place only if new fields arrive,
  // but the common path is "seen → skip". We keep append-only semantics and let query dedup by key
  // (latest wins), so re-appending the same key is cheap and history is preserved.
  const rec = { id: `${type}:${key}`, type, key, title };
  const ts = arg("--ts");
  if (ts) rec.ts = Number(ts);
  const tags = list(arg("--tags"));
  if (tags.length) rec.tags = tags;
  for (const [flag, field] of [["--severity", "severity"], ["--verdict", "verdict"], ["--ref", "ref"], ["--body", "body"]]) {
    const v = arg(flag);
    if (v !== undefined) rec[field] = v;
  }
  appendRecord(store, rec);
  process.stdout.write(rec.id + "\n");
  process.exit(0);
}

// Latest record per identity wins (append-only history, deduped view). Identity is `id`
// (= type:key), NOT key alone — so a `verdict` about a finding coexists with the `finding`
// itself instead of overwriting it. `seen` still matches across types by key.
function dedupById(records) {
  const byId = new Map();
  for (const r of records) byId.set(r.id || `${r.type}:${r.key}`, r);
  return [...byId.values()];
}

function scoreRecord(r, { tags, text }) {
  let score = 0;
  if (tags.length && Array.isArray(r.tags)) {
    for (const t of tags) if (r.tags.includes(t)) score += 3; // tag overlap is the strongest signal
  }
  if (text) {
    const hay = `${r.title || ""} ${r.body || ""}`.toLowerCase();
    for (const term of text.toLowerCase().split(/\s+/).filter(Boolean)) {
      if (hay.includes(term)) score += 1;
    }
  }
  // Recency is a tiebreaker applied in the sort (by r.ts), never in the relevance score itself.
  return score;
}

function cmdQuery(store) {
  const type = arg("--type");
  const tags = list(arg("--tags"));
  const text = arg("--text");
  const limit = Number(arg("--limit", "10"));
  const json = hasFlag("--json");

  let records = dedupById(readAll(store));
  if (type) records = records.filter((r) => r.type === type);

  const hasFilter = tags.length > 0 || !!text;
  const scored = records
    .map((r) => ({ r, s: scoreRecord(r, { tags, text }) }))
    // With an explicit tag/text filter, a zero score means "no match" → exclude it. Without any
    // filter, every score is 0 and we fall back to pure recency order (most recent first).
    .filter((x) => (hasFilter ? x.s > 0 : true))
    .sort((a, b) => b.s - a.s || (b.r.ts || 0) - (a.r.ts || 0))
    .slice(0, limit)
    .map((x) => x.r);

  if (json) {
    process.stdout.write(JSON.stringify(scored) + "\n");
  } else {
    for (const r of scored) {
      const bits = [r.type.toUpperCase(), r.severity && `[${r.severity}]`, r.verdict && `<${r.verdict}>`, r.title]
        .filter(Boolean)
        .join(" ");
      process.stdout.write(`${bits}${r.tags ? "  #" + r.tags.join(" #") : ""}\n`);
    }
  }
  process.exit(0);
}

function cmdSeen(store) {
  const key = arg("--key");
  if (!key) die("--key <k> is required");
  const found = readAll(store).some((r) => r.key === key);
  process.exit(found ? 0 : 1);
}

function cmdStats(store) {
  const records = dedupById(readAll(store));
  const byType = {};
  for (const r of records) byType[r.type] = (byType[r.type] || 0) + 1;
  const out = { store, unique: records.length, byType };
  if (hasFlag("--json")) process.stdout.write(JSON.stringify(out) + "\n");
  else {
    process.stdout.write(`loop memory ${store}\n  unique observations: ${records.length}\n`);
    for (const [t, n] of Object.entries(byType)) process.stdout.write(`  ${t}: ${n}\n`);
  }
  process.exit(0);
}

function main() {
  const mode = process.argv[2];
  const store = arg("--store");
  switch (mode) {
    case "append": return cmdAppend(store);
    case "query": return cmdQuery(store);
    case "seen": return cmdSeen(store);
    case "stats": return cmdStats(store);
    default:
      die("usage: loop-memory.js <append|query|seen|stats> --store <path> [...]");
  }
}

main();
