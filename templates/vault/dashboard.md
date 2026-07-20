---
tags:
  - interview-prep
---

# Interview Prep Dashboard

## ⚡ Log

```dataviewjs
// One-click access to every PrepDojo QuickAdd flow (hotkeys still work too).
// Grouped and color-coded; accents use a colored edge + faint tint so they
// stay readable in both light and dark themes.
const wrap = dv.container.createEl("div");

wrap.createEl("div", { text:
  "Click a button to log an entry.",
  attr: { style: "font-size: 0.8em; font-style: italic; color: #8a8a8a; margin: 0 0 6px 0;" } });

const section = (title) => {
  const g = wrap.createEl("div", { attr: { style: "margin: 8px 0 10px 0;" } });
  g.createEl("div", { text: title, attr: { style:
    "font-size: 0.9em; font-weight: 600; color: var(--text-accent); margin-bottom: 5px;" } });
  return g;
};
const row = (parent, label) => {
  const r = parent.createEl("div", { attr: { style:
    "display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin: 3px 0;" } });
  if (label) r.createEl("span", { text: label, attr: { style:
    "font-size: 0.72em; color: var(--text-muted); min-width: 78px; " +
    "text-transform: uppercase; letter-spacing: 0.05em;" } });
  return r;
};

const mk = (row, label, choice, color) => {
  const b = row.createEl("button", { text: label, attr: { style:
    `border-left: 3px solid ${color}; background: ${color}1f; border-radius: 5px;` } });
  b.onclick = async () => {
    const qa = app.plugins.plugins.quickadd;
    if (!qa || !qa.api || !qa.api.executeChoice) {
      new Notice("QuickAdd isn't available — is the plugin enabled?"); return;
    }
    const known = (qa.settings?.choices || []).some(c => c.name === choice);
    if (!known) {
      new Notice("QuickAdd choice '" + choice + "' not found — deploy PrepDojo's QuickAdd config (see README → Updating).");
      return;
    }
    // Cancelling a prompt rejects the promise; that's normal, not an error.
    try { await qa.api.executeChoice(choice); }
    catch (e) { console.debug("PrepDojo: choice cancelled or failed", e); }
  };
};

const practice = section("What did you practice today?");
const coding = row(practice, "Coding");
mk(coding, "＋ @@NAME_LC@@", "Log @@NAME_LC@@", "#4c9aff");
mk(coding, "＋ @@NAME_MLCODE@@", "Log @@NAME_MLCODE@@", "#9f7fff");
const knowledge = row(practice, "Knowledge");
mk(knowledge, "＋ @@NAME_MLFUND@@", "Log @@NAME_MLFUND@@", "#36b37e");
mk(knowledge, "＋ @@NAME_MLSYS@@", "Log @@NAME_MLSYS@@", "#ff991f");
const behavioral = row(practice, "Behavioral");
mk(behavioral, "＋ @@NAME_BQ@@", "Log @@NAME_BQ@@", "#ff7eb6");

const jobs = section("Where did you apply today?");
const jobsRow = row(jobs, "");
mk(jobsRow, "＋ Application", "Log Application", "#00b8d9");
mk(jobsRow, "＋ Resume version", "Add Resume Version", "#8993a4");
```

<br>

---

## 📊 Stats

```dataviewjs
// Recomputes when the note renders AND when applications.csv changes on disk
// (CSV edits don't touch Dataview's index, so without polling the streak and
// Applications row would go stale while the note is open).
const CSV_PATH = "@@APPLICATIONS_FOLDER@@/applications.csv";

async function render() {
  dv.container.innerHTML = "";
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

  // job applications: count for the streak and for their own Stats row
  let appsTotal = null, appsWeek = 0;
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
        row.push(cell); if (row.length > 7) cells.push(row[7]); row = []; cell = "";
      } else cell += c;
    }
    if (row.length > 7) cells.push(row[7]);
    appsTotal = Math.max(0, cells.length - 1); // all rows; header excluded
    for (let v of cells.slice(1)) { // skip header
      v = (v || "").trim();
      const m = /^(\d{1,2})\/(\d{1,2})\/(\d{2,4})$/.exec(v);
      if (m) v = `${m[3].length === 2 ? "20" + m[3] : m[3]}-${m[1].padStart(2, "0")}-${m[2].padStart(2, "0")}`;
      if (/^\d{4}-\d{2}-\d{2}$/.test(v)) {
        activeDays.add(v);
        const d = dv.date(v);
        if (d && d >= weekAgo && d <= now) appsWeek++;
      }
    }
  } catch (e) { /* no applications.csv — prep-only streak, no Applications row */ }

  // streak: consecutive days (ending today or yesterday) with ≥1 prep entry OR application
  let streak = 0;
  let d = activeDays.has(now.toFormat("yyyy-MM-dd")) ? now : now.minus({ days: 1 });
  while (activeDays.has(d.toFormat("yyyy-MM-dd"))) { streak++; d = d.minus({ days: 1 }); }

  dv.paragraph(`**🔥 Streak: ${streak} day${streak === 1 ? "" : "s"}** (prep or applications) · Active days total: ${activeDays.size}`);
  const statRows = Object.keys(tags).map(t => [tags[t], week[t], total[t]]);
  if (appsTotal !== null) statRows.unshift(["Applications", appsWeek, appsTotal]);
  dv.table(["Category", "Last 7 days", "All time"], statRows);
}

let lastMtime = -1;
async function tick() {
  let m = 0;
  try { const st = await app.vault.adapter.stat(CSV_PATH); m = st ? st.mtime : 0; }
  catch (e) { /* no CSV; render once with m = 0 */ }
  if (m !== lastMtime) { lastMtime = m; await render(); }
}
await tick();
const pollId = window.setInterval(async () => {
  if (!dv.container.isConnected) { window.clearInterval(pollId); return; }
  try { await tick(); } catch (e) { /* file mid-write; retry next tick */ }
}, 3000);
```

<br>

---

## 💼 Job Applications

> [!note]- Where this data lives
> Source: `@@APPLICATIONS_FOLDER@@/applications.csv` (+ `resume-versions.csv`). Log with the ＋ Application button (or `prepdojo apps log`, a CSV editor, any spreadsheet app — all write the same file); this section re-reads it and updates live while the note is open.

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

let rangeDays = null; // view state only; null = all time (rates need the full funnel)

async function render() {
  const apps = parseCSV(await app.vault.adapter.read(PATH));
  for (const r of apps) r["Applied Date"] = normDate(r["Applied Date"]);
  dv.container.innerHTML = "";
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
  // headline left, log buttons right (same flows as the Log bar up top)
  const head = dv.container.createEl("div", { attr: { style:
    "display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 0 0 6px 0;" } });
  const headText = head.createEl("span");
  headText.createEl("strong", { text: `📨 Today: ${todayN}` });
  headText.appendText(` · last 7 days: ${weekN} · total: ${apps.length}`);
  const headBtns = head.createEl("span", { attr: { style:
    "margin-left: auto; display: flex; gap: 6px;" } });
  const qaBtn = (label, choice, color) => {
    const b = headBtns.createEl("button", { text: label, attr: { style:
      `border-left: 3px solid ${color}; background: ${color}1f; border-radius: 5px;` } });
    b.onclick = async () => {
      const qa = app.plugins.plugins.quickadd;
      if (!qa || !qa.api || !qa.api.executeChoice) {
        new Notice("QuickAdd isn't available — is the plugin enabled?"); return;
      }
      if (!(qa.settings?.choices || []).some(c => c.name === choice)) {
        new Notice("QuickAdd choice '" + choice + "' not found — deploy PrepDojo's QuickAdd config (see README → Updating).");
        return;
      }
      try { await qa.api.executeChoice(choice); }
      catch (e) { console.debug("PrepDojo: choice cancelled or failed", e); }
    };
  };
  qaBtn("＋ Application", "Log Application", "#00b8d9");
  qaBtn("＋ Resume version", "Add Resume Version", "#8993a4");

  // range chips: filter Pipeline / Responses / By resume version by Applied Date
  const bar = dv.container.createEl("div", { attr: { style:
    "display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin: 28px 0 6px 0;" } });
  for (const [label, days] of [["7d", 7], ["14d", 14], ["30d", 30], ["90d", 90], ["All", null]]) {
    const active = days === rangeDays;
    const chip = bar.createEl("button", { text: label, attr: { style:
      "border-radius: 5px; padding: 2px 10px;"
      + (active ? " background: var(--interactive-accent); color: var(--text-on-accent);" : "") } });
    chip.onclick = () => { rangeDays = days; render(); };
  }
  const cutoff = rangeDays === null ? null : now.minus({ days: rangeDays - 1 });
  const rows = cutoff === null ? apps : apps.filter(r => {
    const d = dv.date(r["Applied Date"]);
    return d && d >= cutoff && d <= now;
  });
  const undated = cutoff === null ? 0 : apps.filter(r => !dv.date(r["Applied Date"])).length;
  const rangeText = cutoff === null
    ? `Showing all ${apps.length} applications`
    : `Showing last ${rangeDays} days (${cutoff.toFormat("yyyy-MM-dd")} – ${now.toFormat("yyyy-MM-dd")}) · ${rows.length} applications`
      + (undated ? ` · ${undated} without a date excluded` : "");
  dv.container.createEl("div", { text: rangeText, attr: { style:
    "font-size: 0.8em; font-style: italic; color: #8a8a8a; margin: 0 0 8px 0;" } });

  // pipeline: count by current status
  const byStatus = {};
  for (const r of rows) byStatus[r["Status"] || "—"] = (byStatus[r["Status"] || "—"] ?? 0) + 1;
  const active = ["Applied", "OA", "Phone Screen", "Onsite", "Team Match"]
    .reduce((s, k) => s + (byStatus[k] ?? 0), 0);
  dv.header(3, "Pipeline");
  dv.paragraph(`Active (in pipeline): **${active}**`);
  dv.table(["Status", "Count"],
    Object.entries(byStatus).sort((a, b) => b[1] - a[1]));

  // milestones ever reached (from stage history)
  const ever = s => rows.filter(r => (r["Stage History"] || "").toLowerCase()
    .includes(s.toLowerCase())).length;
  const nInt = rows.filter(interviewed).length;
  dv.header(3, "Responses");
  dv.table(["Milestone", "Count", "Rate"], [
    ["Ever Phone Screen", ever("Phone Screen"), ""],
    ["Ever Onsite", ever("Onsite"), ""],
    ["Ever Offer", ever("Offer"), ""],
    ["Ever interviewed (≥1 round)", nInt, rows.length ? (100 * nInt / rows.length).toFixed(1) + "%" : "—"],
    ["Rejected", byStatus["Rejected"] ?? 0, ""],
  ]);

  // by resume version: usage + interview rate
  const byVer = {};
  for (const r of rows) {
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

<br>

---

## 🧩 @@NAME_LC@@

> [!note]- Where this data lives
> Source: your daily notes in `@@DAILY_NOTES_FOLDER@@/`, as plain bullets under `@@PREP_HEADING@@`, e.g. `- LC #200 Number of Islands · Medium · bfs/dfs #@@TAG_LC@@`. The Import and ＋ buttons write there for you; you can also type entries directly. This section recomputes from those notes every time it renders.

```dataviewjs
// Range-filtered view of logged problems, with one-click import of recent
// accepted submissions (same behavior as `prepdojo sync-lc`).
const LC_USERNAME = "@@LC_USERNAME@@";
let rangeDays = 7; // view state only — resets to the default when the note reopens

async function lcRenderNewNote(d) {
  const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const days = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
  const months = ["January","February","March","April","May","June","July",
                  "August","September","October","November","December"];
  const fmt = f => f.replace(/dddd/g, days[d.getDay()]).replace(/MMMM/g, months[d.getMonth()])
    .replace(/YYYY/g, d.getFullYear()).replace(/MM/g, String(d.getMonth() + 1).padStart(2, "0"))
    .replace(/DD/g, String(d.getDate()).padStart(2, "0")).replace(/\bD\b/g, d.getDate());
  let t;
  try { t = await app.vault.adapter.read("@@DAILY_NOTE_TEMPLATE@@"); }
  catch (e) { t = "# {{date:dddd, MMMM D, YYYY}}\n\n@@PREP_HEADING@@\n"; }
  return t.replace(/\{\{date:([^}]*)\}\}/g, (_, f) => fmt(f))
          .replace(/\{\{date\}\}/g, iso);
}

async function lcInsertEntry(d, entry) {
  const days2 = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
  const months2 = ["January","February","March","April","May","June","July",
                   "August","September","October","November","December"];
  const fname = "@@DATE_FORMAT@@".replace(/dddd/g, days2[d.getDay()])
    .replace(/MMMM/g, months2[d.getMonth()]).replace(/YYYY/g, d.getFullYear())
    .replace(/MM/g, String(d.getMonth() + 1).padStart(2, "0"))
    .replace(/DD/g, String(d.getDate()).padStart(2, "0")).replace(/\bD\b/g, d.getDate());
  const path = "@@DAILY_NOTES_FOLDER@@/" + fname + ".md";
  const heading = "@@PREP_HEADING@@";
  let content = (await app.vault.adapter.exists(path))
    ? await app.vault.adapter.read(path) : await lcRenderNewNote(d);
  const lines = content.split("\n");
  let start = lines.indexOf(heading);
  if (start === -1) { lines.push("", heading, ""); start = lines.indexOf(heading); }
  start += 1;
  let end = start;
  const level = heading.split(" ")[0] + " ";
  while (end < lines.length && !lines[end].startsWith(level)) end++;
  const keyOf = s2 => { const m = /#\s*(\d+)|\b(\d+)\./.exec(s2); return m ? (m[1] || m[2]) : null; };
  const key = keyOf(entry);
  for (let i = start; i < end; i++) {
    if (lines[i].trim() === entry.trim()) return "dup";
    if (key && lines[i].includes("#@@TAG_LC@@") && keyOf(lines[i]) === key) return "dup";
  }
  let at = start;
  for (let i = start; i < end; i++) if (lines[i].trim()) at = i + 1;
  if (at === start && (start >= lines.length || lines[start].trim() !== "")) {
    lines.splice(start, 0, ""); at = start + 1;
  }
  lines.splice(at, 0, entry);
  await app.vault.adapter.write(path, lines.join("\n"));
  return "new";
}

async function lcImport(btn) {
  if (!LC_USERNAME) {
    new Notice("Set username under [leetcode] in config.toml, then redeploy (see README → Updating).");
    return;
  }
  const { requestUrl } = require("obsidian");
  const gql = async (query, variables) => {
    const r = await requestUrl({ url: "https://leetcode.com/graphql", method: "POST",
      headers: { "Content-Type": "application/json", "Referer": "https://leetcode.com" },
      body: JSON.stringify({ query, variables }), throw: false });
    const dta = r.json && r.json.data;
    if (!dta) throw new Error("unexpected LeetCode response");
    return dta;
  };
  btn.disabled = true; const old = btn.textContent; btn.textContent = "Importing…";
  try {
    const recent = (await gql(
      "query($u:String!,$l:Int!){recentAcSubmissionList(username:$u,limit:$l){title titleSlug timestamp}}",
      { u: LC_USERNAME, l: 20 })).recentAcSubmissionList;
    if (!recent) throw new Error("no submissions — private profile or wrong username?");
    const since = new Date(); since.setDate(since.getDate() - 7); since.setHours(0, 0, 0, 0);
    const qcache = {};
    let added = 0, dups = 0;
    for (const sub of recent) {
      const d = new Date(parseInt(sub.timestamp) * 1000);
      if (d < since) continue;
      if (!qcache[sub.titleSlug]) {
        qcache[sub.titleSlug] = (await gql(
          "query($s:String!){question(titleSlug:$s){questionFrontendId title difficulty}}",
          { s: sub.titleSlug })).question;
      }
      const q = qcache[sub.titleSlug];
      if (!q) continue;
      const entry = `- LC #${q.questionFrontendId} ${q.title} · ${q.difficulty} #@@TAG_LC@@`;
      (await lcInsertEntry(d, entry)) === "dup" ? dups++ : added++;
    }
    new Notice(`LeetCode import: ${added} new, ${dups} already logged.`
      + (added ? " New entries need topics." : ""));
  } catch (e) {
    new Notice("LeetCode import failed: " + e.message + " — nothing was changed.");
  } finally {
    btn.disabled = false; btn.textContent = old;
  }
}

const TOPICS = "@@TOPICS_CSV@@".split(",");

async function addTopic(r, btn) {
  const qa = app.plugins.plugins.quickadd;
  if (!qa || !qa.api || !qa.api.suggester) {
    new Notice("QuickAdd isn't available — is the plugin enabled?"); return;
  }
  let topic;
  try { topic = await qa.api.suggester(TOPICS, TOPICS); }
  catch (e) { return; } // picker cancelled — nothing to do
  if (!topic) return;
  const path = "@@DAILY_NOTES_FOLDER@@/" + r.day + ".md";
  let raw;
  try { raw = await app.vault.adapter.read(path); }
  catch (e) { new Notice("Couldn't open " + r.day + "'s note."); return; }
  const lines = raw.split("\n");
  const keyOf = s => { const m = /#\s*(\d+)|\b(\d+)\./.exec(s); return m ? (m[1] || m[2]) : null; };
  const rkey = keyOf(r.problem);
  let done = false;
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (!l.includes("#@@TAG_LC@@")) continue;
    const match = rkey ? keyOf(l) === rkey : l.includes(r.problem);
    if (!match || l.split("\u00b7").length >= 3) continue; // wrong entry, or topic already set
    lines[i] = l.replace(/\s*#@@TAG_LC@@/, " \u00b7 " + topic + " #@@TAG_LC@@");
    done = true; break;
  }
  if (!done) {
    new Notice("Couldn't find that entry — it may have been edited. Add the topic in the daily note.");
    return;
  }
  await app.vault.adapter.write(path, lines.join("\n"));
  new Notice(r.problem + " \u2192 " + topic);
}

function render() {
  dv.container.innerHTML = "";

  // two ways to log, then the range chips on their own row
  dv.container.createEl("div", { text:
    "Two ways to log: import your accepted LeetCode submissions (last 7 days, up to the 20 most recent), or add a solve by hand.",
    attr: { style: "font-size: 0.8em; font-style: italic; color: #8a8a8a; margin: 0 0 6px 0;" } });
  const bar = dv.container.createEl("div", { attr: { style:
    "display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin: 0 0 6px 0;" } });
  const imp = bar.createEl("button", { text: "⟳ Import from LeetCode", attr: { style:
    "border-left: 3px solid #4c9aff; background: #4c9aff1f; border-radius: 5px;" } });
  imp.onclick = () => lcImport(imp);
  bar.createEl("span", { text: "or", attr: { style:
    "font-size: 0.8em; color: var(--text-muted);" } });
  const manual = bar.createEl("button", { text: "＋ @@NAME_LC@@", attr: { style:
    "border-left: 3px solid #4c9aff; background: #4c9aff1f; border-radius: 5px;" } });
  manual.onclick = async () => {
    const qa = app.plugins.plugins.quickadd;
    if (!qa || !qa.api || !qa.api.executeChoice) {
      new Notice("QuickAdd isn't available — is the plugin enabled?"); return;
    }
    if (!(qa.settings?.choices || []).some(c => c.name === "Log @@NAME_LC@@")) {
      new Notice("QuickAdd choice 'Log @@NAME_LC@@' not found — deploy PrepDojo's QuickAdd config (see README → Updating).");
      return;
    }
    try { await qa.api.executeChoice("Log @@NAME_LC@@"); }
    catch (e) { console.debug("PrepDojo: choice cancelled or failed", e); }
  };
  const chipRow = dv.container.createEl("div", { attr: { style:
    "display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin: 28px 0 6px 0;" } });
  for (const [label, days] of [["7d", 7], ["14d", 14], ["30d", 30], ["90d", 90], ["All", null]]) {
    const active = days === rangeDays;
    const chip = chipRow.createEl("button", { text: label, attr: { style:
      "border-radius: 5px; padding: 2px 10px;"
      + (active ? " background: var(--interactive-accent); color: var(--text-on-accent);" : "") } });
    chip.onclick = () => { rangeDays = days; render(); };
  }

  // parse all logged problems
  const logged = i => !i.task || i.completed;
  const all = [];
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
      all.push({ day: p.file.name, link: p.file.link,
        problem: parts[0] || "—",
        diff: diffMap[rawDiff] ?? rawDiff,
        topic: fullTopic,
        mainTopic: fullTopic.split(" - ")[0].trim(),
        notes: parts.slice(3).join(" · ") || "—" });
    }
  }
  all.sort((a, b) => b.day.localeCompare(a.day));

  // range filter (the tables below); Needs topic stays all-time on purpose
  const now = dv.date("today");
  const cutoff = rangeDays === null ? null : now.minus({ days: rangeDays - 1 });
  const rows = cutoff === null ? all
    : all.filter(r => { const d = dv.date(r.day); return d && d >= cutoff && d <= now; });
  const rangeText = rangeDays === null
    ? `Showing all time · ${rows.length} solves`
    : `Showing last ${rangeDays} days (${cutoff.toFormat("yyyy-MM-dd")} – ${now.toFormat("yyyy-MM-dd")}) · ${rows.length} solves`;
  dv.container.createEl("div", { text: rangeText, attr: { style:
    "font-size: 0.8em; font-style: italic; color: #8a8a8a; margin: 0 0 8px 0;" } });

  // Needs topic: all-time todo list, unaffected by the range.
  // Each row has a picker that writes the topic into the entry — no manual editing.
  const untopiced = all.filter(r => r.topic === "—");
  if (untopiced.length) {
    dv.header(3, "Needs topic");
    dv.container.createEl("div", { text:
      "Imported entries don't say how you solved the problem. Pick a topic and it's filled in for you.",
      attr: { style: "font-size: 0.8em; font-style: italic; color: #8a8a8a; margin: 0 0 6px 0;" } });
    for (const r of untopiced) {
      const rowEl = dv.container.createEl("div", { attr: { style:
        "display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin: 3px 0;" } });
      const a = rowEl.createEl("a", { text: r.day, attr: { style: "min-width: 88px;" } });
      a.onclick = () => app.workspace.openLinkText(r.day, "", false);
      rowEl.createEl("span", { text: `${r.problem} · ${r.diff}` });
      const b = rowEl.createEl("button", { text: "＋ Topic", attr: { style:
        "border-left: 3px solid #4c9aff; background: #4c9aff1f; border-radius: 5px; padding: 1px 10px;" } });
      b.onclick = () => addTopic(r, b);
    }
  }

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

  // Problems in range
  dv.header(3, "Problems");
  dv.table(["Date", "Problem", "Difficulty", "Topic", "Notes"],
    rows.map(r => [r.link, r.problem, r.diff, r.topic, r.notes]));
}

render();
```

<br>

---

## 📚 @@NAME_MLFUND@@

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

<br>

---

## ⚙️ @@NAME_MLCODE@@ & @@NAME_MLSYS@@

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

<br>

---

## 💬 @@NAME_BQ@@

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
