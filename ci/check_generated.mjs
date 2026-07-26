#!/usr/bin/env node
/* Static checks on generated output. Run after `python3 generate.py --no-install`.
 *
 * 1. Every QuickAdd user script in dist/vault/scripts parses as JavaScript.
 * 2. Every dataviewjs block in every generated markdown file parses.
 * 3. QuickAdd data.json is valid, choice ids/names are unique, and every
 *    choice name the dashboard invokes via executeChoice exists.
 *
 * Usage: node ci/check_generated.mjs [distDir]   (default: dist)
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const dist = process.argv[2] || "dist";
let failures = 0;
const ok = (cond, label) => {
  console.log((cond ? "  ok  " : "  FAIL") + "  " + label);
  if (!cond) failures++;
};

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* walk(p);
    else yield p;
  }
}

// 1. user scripts parse
console.log("QuickAdd user scripts");
for (const p of walk(join(dist, "vault", "scripts"))) {
  if (!p.endsWith(".js")) continue;
  try { new Function(readFileSync(p, "utf8")); ok(true, p); }
  catch (e) { ok(false, `${p}: ${e.message}`); }
}

// 2. dataviewjs blocks parse (async context, like Dataview provides)
console.log("dataviewjs blocks");
for (const p of walk(join(dist, "vault"))) {
  if (!p.endsWith(".md")) continue;
  const text = readFileSync(p, "utf8");
  const blocks = [...text.matchAll(/```dataviewjs\n([\s\S]*?)```/g)];
  blocks.forEach((m, i) => {
    try {
      new Function("dv", "app", "Notice", "window", "document", "require",
        "return (async () => {\n" + m[1] + "\n})");
      ok(true, `${p} block ${i + 1}`);
    } catch (e) { ok(false, `${p} block ${i + 1}: ${e.message}`); }
  });
}

// 3. data.json contract
console.log("QuickAdd data.json contract");
const dataPath = join(dist, "obsidian", "plugins", "quickadd", "data.json");
let data;
try { data = JSON.parse(readFileSync(dataPath, "utf8")); ok(true, "valid JSON"); }
catch (e) { ok(false, "data.json: " + e.message); process.exit(1); }
const choices = data.choices || [];
const ids = choices.map(c => c.id);
const names = choices.map(c => c.name);
ok(new Set(ids).size === ids.length, "choice ids unique");
ok(new Set(names).size === names.length, "choice names unique");

// every name the dashboard calls must exist
const invoked = new Set();
for (const p of walk(join(dist, "vault"))) {
  if (!p.endsWith(".md")) continue;
  const text = readFileSync(p, "utf8");
  for (const m of text.matchAll(/executeChoice\("([^"]+)"\)/g)) invoked.add(m[1]);
  for (const m of text.matchAll(/c\.name === "([^"]+)"/g)) invoked.add(m[1]);
  for (const m of text.matchAll(/executeChoice\(choice\)/g)) { /* dynamic: covered below */ }
  // Log-bar mk() calls pass the choice name as the 3rd string argument
  for (const m of text.matchAll(/mk\([^,]+, "[^"]+", "([^"]+)"/g)) invoked.add(m[1]);
}
for (const name of invoked) {
  ok(names.includes(name), `dashboard-invoked choice exists: "${name}"`);
}

if (failures) { console.log(`\n${failures} check(s) FAILED`); process.exit(1); }
console.log("\nall generated-output checks passed");
