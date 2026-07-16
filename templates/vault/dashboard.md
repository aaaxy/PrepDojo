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

// streak: consecutive days (ending today or yesterday) with ≥1 logged entry
let streak = 0;
let d = activeDays.has(now.toFormat("yyyy-MM-dd")) ? now : now.minus({ days: 1 });
while (activeDays.has(d.toFormat("yyyy-MM-dd"))) { streak++; d = d.minus({ days: 1 }); }

dv.paragraph(`**🔥 Streak: ${streak} day${streak === 1 ? "" : "s"}** · Active days total: ${activeDays.size}`);
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
