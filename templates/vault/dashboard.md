---
tags: [interview-prep]
---

# Interview Prep Dashboard

> How to log: QuickAdd hotkey → pick day → fill prompts. Entries are plain bullets under `@@PREP_HEADING@@` ending in a tag, e.g. `- LC #200 Number of Islands · Medium · bfs/dfs #@@TAG_LC@@`. Checked tasks also count (legacy); unchecked boxes are ignored as placeholders.

## Stats

```dataviewjs
const tags = {"#@@TAG_LC@@": "@@NAME_LC@@", "#@@TAG_MLFUND@@": "@@NAME_MLFUND@@", "#@@TAG_MLCODE@@": "@@NAME_MLCODE@@", "#@@TAG_MLSYS@@": "@@NAME_MLSYS@@", "#@@TAG_BQ@@": "@@NAME_BQ@@"};
const logged = i => !i.task || i.completed; // plain bullet, or checked task (legacy)
const now = dv.date("today");
const weekAgo = now.minus({ days: 6 });

let total = {}, week = {}, activeDays = new Set();
for (const t in tags) { total[t] = 0; week[t] = 0; }

for (const p of dv.pages('"@@DAILY_NOTES_FOLDER@@"')) {
  const day = dv.date(p.file.name);
  if (!day) continue;
  for (const item of p.file.lists.filter(logged)) {
    for (const t in tags) {
      if (item.text.includes(t)) {
        total[t]++;
        activeDays.add(p.file.name);
        if (day >= weekAgo && day <= now) week[t]++;
      }
    }
  }
}

// job applications count as activity too (combined "did anything" streak)
try {
  const raw = await app.vault.adapter.read("@@APPLICATIONS_FOLDER@@/applications.csv");
  // one compact pass: collect the Applied Date column (col 8) respecting quotes
  const cells = []; let row = [], cell = "", inQ = false;
  for (let i = 0; i < raw.length; i++) {
    const c = raw[i];
    if (inQ) {
      if (c === '"' && raw[i + 1] === '"') { cell += '"'; i++; }
      else if (c === '"') inQ = false;
      else cell += c;
    } else if (c === '"') inQ = true;
    else if (c === ",") { row.push(cell); cell = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && raw[i + 1] === "\n") i++;
      row.push(cell); if (row.length > 7 && row[7]) cells.push(row[7]); row = []; cell = "";
    } else cell += c;
  }
  if (row.length > 7 && row[7]) cells.push(row[7]);
  for (let v of cells.slice(1)) { // skip header
    const m = /^(\d{1,2})\/(\d{1,2})\/(\d{2,4})$/.exec(v.trim());
    if (m) v = `${m[3].length === 2 ? "20" + m[3] : m[3]}-${m[1].padStart(2, "0")}-${m[2].padStart(2, "0")}`;
    if (/^\d{4}-\d{2}-\d{2}$/.test(v.trim())) activeDays.add(v.trim());
  }
} catch (e) { /* no applications.csv — prep-only streak */ }

// streak: consecutive days (ending today or yesterday) with ≥1 prep entry OR application
let streak = 0;
let d = activeDays.has(now.toFormat("yyyy-MM-dd")) ? now : now.minus({ days: 1 });
while (activeDays.has(d.toFormat("yyyy-MM-dd"))) { streak++; d = d.minus({ days: 1 }); }

dv.paragraph(`**🔥 Streak: ${streak} day${streak === 1 ? "" : "s"}** (prep or applications) · Active days total: ${activeDays.size}`);
dv.table(["Category", "Last 7 days", "All time"],
  Object.keys(tags).map(t => [tags[t], week[t], total[t]]));
```

## This week

```dataviewjs
const tags = ["#@@TAG_LC@@", "#@@TAG_MLFUND@@", "#@@TAG_MLCODE@@", "#@@TAG_MLSYS@@", "#@@TAG_BQ@@"];
const logged = i => !i.task || i.completed;
const weekAgo = dv.date("today").minus({ days: 6 });
const rows = [];
for (const p of dv.pages('"@@DAILY_NOTES_FOLDER@@"')) {
  const day = dv.date(p.file.name);
  if (!day || day < weekAgo) continue;
  for (const i of p.file.lists.filter(i => logged(i) && tags.some(t => i.text.includes(t))))
    rows.push({ day: p.file.name, link: p.file.link, text: i.text });
}
rows.sort((a, b) => b.day.localeCompare(a.day));
dv.table(["Date", "Entry"], rows.map(r => [r.link, r.text]));
```

## Job Applications

> Source: `@@APPLICATIONS_FOLDER@@/applications.csv` (+ `resume-versions.csv`). Log there via `prepdojo apps log`, a CSV editor plugin, or any spreadsheet app; this section re-reads the file and updates live while the note is open.

```dataviewjs
// Self-refreshing: reads the CSV uncached (dv.io.csv caches and misses
// external edits), then polls the file's mtime while this note is open
// and re-renders whenever it changes.
const PATH = "@@APPLICATIONS_FOLDER@@/applications.csv";

function parseCSV(text) {
  const rows = []; let row = [], cell = "", inQ = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQ) {
      if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; }
      else if (c === '"') inQ = false;
      else cell += c;
    } else if (c === '"') inQ = true;
    else if (c === ",") { row.push(cell); cell = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(cell); cell = "";
      if (row.some(x => x !== "")) rows.push(row);
      row = [];
    } else cell += c;
  }
  if (cell !== "" || row.length) { row.push(cell); if (row.some(x => x !== "")) rows.push(row); }
  const header = rows.shift() ?? [];
  return rows.map(r => Object.fromEntries(header.map((h, i) => [h, r[i] ?? ""])));
}

// tolerate spreadsheet-app date rewrites: "7/16/26" or "7/16/2026" → "2026-07-16"
function normDate(v) {
  const m = /^(\d{1,2})\/(\d{1,2})\/(\d{2,4})$/.exec((v || "").trim());
  if (!m) return (v || "").trim();
  const y = m[3].length === 2 ? "20" + m[3] : m[3];
  return `${y}-${m[1].padStart(2, "0")}-${m[2].padStart(2, "0")}`;
}

function quickActionButtons() {
  // Buttons that fire the PrepDojo QuickAdd choices — same flows as the
  // hotkey / command palette, one click from the dashboard.
  const bar = dv.container.createEl("div",
    { attr: { style: "margin: 4px 0 12px 0; display: flex; gap: 8px;" } });
  const mk = (label, choice) => {
    const b = bar.createEl("button", { text: label });
    b.onclick = async () => {
      const qa = app.plugins.plugins.quickadd;
      if (!qa || !qa.api || !qa.api.executeChoice) {
        new Notice("QuickAdd isn't available — is the plugin enabled?"); return;
      }
      try { await qa.api.executeChoice(choice); }
      catch (e) {
        new Notice("QuickAdd choice '" + choice + "' not found — deploy PrepDojo's QuickAdd config (see README → Updating).");
      }
    };
  };
  mk("＋ Log application", "Log Application");
  mk("＋ Add resume version", "Add Resume Version");
}

async function render() {
  const apps = parseCSV(await app.vault.adapter.read(PATH));
  for (const r of apps) r["Applied Date"] = normDate(r["Applied Date"]);
  dv.container.innerHTML = "";
  quickActionButtons();
  if (!apps.length) { dv.paragraph("*No applications logged yet.*"); return; }
  const now = dv.date("today");
  const weekAgo = now.minus({ days: 6 });
  const interviewed = r => /Phone Screen|Onsite|Team Match|Offer/i.test(r["Stage History"] || "");

  // headline: velocity
  const dated = apps.filter(r => r["Applied Date"]);
  const perDay = {};
  for (const r of dated) perDay[r["Applied Date"]] = (perDay[r["Applied Date"]] ?? 0) + 1;
  const todayN = perDay[now.toFormat("yyyy-MM-dd")] ?? 0;
  const weekN = dated.filter(r => {
    const d = dv.date(r["Applied Date"]);
    return d && d >= weekAgo && d <= now;
  }).length;
  dv.paragraph(`**📨 Today: ${todayN}** · last 7 days: ${weekN} · total: ${apps.length}`);

  // pipeline: count by current status
  const byStatus = {};
  for (const r of apps) byStatus[r["Status"] || "—"] = (byStatus[r["Status"] || "—"] ?? 0) + 1;
  const active = ["Applied", "OA", "Phone Screen", "Onsite", "Team Match"]
    .reduce((s, k) => s + (byStatus[k] ?? 0), 0);
  dv.header(3, "Pipeline");
  dv.paragraph(`Active (in pipeline): **${active}**`);
  dv.table(["Status", "Count"],
    Object.entries(byStatus).sort((a, b) => b[1] - a[1]));

  // milestones ever reached (from stage history)
  const ever = s => apps.filter(r => (r["Stage History"] || "").toLowerCase()
    .includes(s.toLowerCase())).length;
  const nInt = apps.filter(interviewed).length;
  dv.header(3, "Responses");
  dv.table(["Milestone", "Count", "Rate"], [
    ["Ever Phone Screen", ever("Phone Screen"), ""],
    ["Ever Onsite", ever("Onsite"), ""],
    ["Ever Offer", ever("Offer"), ""],
    ["Ever interviewed (≥1 round)", nInt, (100 * nInt / apps.length).toFixed(1) + "%"],
    ["Rejected", byStatus["Rejected"] ?? 0, ""],
  ]);

  // by resume version: usage + interview rate
  const byVer = {};
  for (const r of apps) {
    const v = r["Resume Version"] || "—";
    (byVer[v] ??= { n: 0, int: 0 });
    byVer[v].n++;
    if (interviewed(r)) byVer[v].int++;
  }
  dv.header(3, "By resume version");
  dv.table(["Version", "Apps", "Interviewed", "Rate"],
    Object.entries(byVer)
      .sort((a, b) => b[1].n - a[1].n)
      .map(([v, s]) => [v, s.n, s.int, s.n ? (100 * s.int / s.n).toFixed(0) + "%" : "—"]));

  // last 14 days
  dv.header(3, "Last 14 days");
  const days = [];
  for (let i = 0; i < 14; i++) {
    const d = now.minus({ days: i }).toFormat("yyyy-MM-dd");
    if (perDay[d]) days.push([d, perDay[d]]);
  }
  dv.table(["Date", "Applications"], days);
}

let lastMtime = 0;
async function tick() {
  const s = await app.vault.adapter.stat(PATH);
  if (s && s.mtime !== lastMtime) { lastMtime = s.mtime; await render(); }
}
await tick();
const pollId = window.setInterval(async () => {
  if (!dv.container.isConnected) { window.clearInterval(pollId); return; }
  try { await tick(); } catch (e) { /* file mid-write; retry next tick */ }
}, 3000);
```

## @@NAME_LC@@

```dataviewjs
const logged = i => !i.task || i.completed;
const rows = [];
for (const p of dv.pages('"@@DAILY_NOTES_FOLDER@@"')) {
  for (const t of p.file.lists.filter(i => logged(i) && i.text.includes("#@@TAG_LC@@"))) {
    const clean = t.text.replace(/#@@TAG_LC@@\b/g, "").replace(/^LC\s*/i, "")
      .replace(/#\s+(\d)/, "#$1").replace(/^(\d+)\.?\s*/, "#$1 ").trim();
    const parts = clean.split("·").map(s => s.trim());
    const diffMap = { "🟢": "Easy", "🟡": "Medium", "🔴": "Hard",
      "E": "Easy", "M": "Medium", "H": "Hard",
      "easy": "Easy", "medium": "Medium", "hard": "Hard" };
    const rawDiff = parts[1] || "—";
    const fullTopic = (parts[2] || "—").toLowerCase();
    rows.push({ day: p.file.name, link: p.file.link,
      problem: parts[0] || "—",
      diff: diffMap[rawDiff] ?? rawDiff,
      topic: fullTopic,
      mainTopic: fullTopic.split(" - ")[0].trim(),
      notes: parts.slice(3).join(" · ") || "—" });
  }
}
rows.sort((a, b) => b.day.localeCompare(a.day));

// By topic (groups by main topic; "dp - knapsack" counts under "dp")
const byTopic = {};
for (const r of rows) (byTopic[r.mainTopic] ??= []).push(r);
dv.header(3, "By topic");
dv.table(["Topic", "Count", "Problems"],
  Object.entries(byTopic)
    .sort((a, b) => b[1].length - a[1].length)
    .map(([topic, rs]) => [topic, rs.length, rs.map(r => r.problem).join(", ")]));

// By difficulty
const byDiff = {};
for (const r of rows) byDiff[r.diff] = (byDiff[r.diff] ?? 0) + 1;
dv.header(3, "By difficulty");
dv.table(["Difficulty", "Count"],
  ["Easy", "Medium", "Hard"].filter(d => byDiff[d])
    .map(d => [d, byDiff[d]])
    .concat(Object.entries(byDiff).filter(([d]) => !["Easy", "Medium", "Hard"].includes(d))));

// Full list
dv.header(3, "All problems");
dv.table(["Date", "Problem", "Difficulty", "Topic", "Notes"],
  rows.map(r => [r.link, r.problem, r.diff, r.topic, r.notes]));
```

## @@NAME_MLFUND@@

```dataviewjs
const logged = i => !i.task || i.completed;
const rows = [];
for (const p of dv.pages('"@@DAILY_NOTES_FOLDER@@"')) {
  for (const t of p.file.lists.filter(i => logged(i) && i.text.includes("#@@TAG_MLFUND@@"))) {
    const clean = t.text.replace(/#@@TAG_MLFUND@@\b/g, "").trim();
    const conf = clean.includes("🔴") ? "🔴" : clean.includes("🟡") ? "🟡" : clean.includes("🟢") ? "🟢" : "—";
    const topic = clean.replace(/[·🟢🟡🔴]/g, "").trim();
    rows.push({ day: p.file.name, link: p.file.link, topic, conf });
  }
}
rows.sort((a, b) => b.day.localeCompare(a.day));

// Needs re-review: latest confidence per topic is 🔴 or 🟡
const latest = {};
for (const r of rows) if (!latest[r.topic]) latest[r.topic] = r.conf; // rows already newest-first
const weak = Object.entries(latest).filter(([, c]) => c === "🔴" || c === "🟡");
dv.header(3, "Needs re-review");
if (weak.length) dv.table(["Topic", "Confidence"], weak);
else dv.paragraph("Nothing flagged — all topics 🟢");

dv.header(3, "All topics reviewed");
dv.table(["Date", "Topic", "Confidence"], rows.map(r => [r.link, r.topic, r.conf]));
```

## @@NAME_MLCODE@@ & @@NAME_MLSYS@@

```dataviewjs
const logged = i => !i.task || i.completed;
const rows = [];
for (const p of dv.pages('"@@DAILY_NOTES_FOLDER@@"')) {
  for (const i of p.file.lists.filter(i => logged(i) && (i.text.includes("#@@TAG_MLCODE@@") || i.text.includes("#@@TAG_MLSYS@@"))))
    rows.push({ day: p.file.name, link: p.file.link,
      type: i.text.includes("#@@TAG_MLCODE@@") ? "coding" : "design",
      text: i.text.replace(/#@@TAG_MLCODE@@\b/g, "").replace(/#@@TAG_MLSYS@@\b/g, "").trim() });
}
rows.sort((a, b) => b.day.localeCompare(a.day));
dv.table(["Date", "Type", "Entry"], rows.map(r => [r.link, r.type, r.text]));
```

## @@NAME_BQ@@

```dataviewjs
const logged = i => !i.task || i.completed;
const rows = [];
for (const p of dv.pages('"@@DAILY_NOTES_FOLDER@@"')) {
  for (const i of p.file.lists.filter(i => logged(i) && i.text.includes("#@@TAG_BQ@@")))
    rows.push({ day: p.file.name, link: p.file.link, text: i.text.replace(/#@@TAG_BQ@@\b/g, "").trim() });
}
rows.sort((a, b) => b.day.localeCompare(a.day));
dv.table(["Date", "Entry"], rows.map(r => [r.link, r.text]));
```
