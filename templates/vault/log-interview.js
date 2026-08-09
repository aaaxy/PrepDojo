/* PrepDojo: log a real interview from inside Obsidian.
 * Generated from config.toml — edit templates/vault/log-interview.js in the
 * PrepDojo repo, not this copy. Runs as a QuickAdd macro user script.
 *
 * Entry shape (Q: marks the questions field; empty fields are omitted):
 *   - <Company — Position> · <round> · Q: <questions> · <reflections> #@@TAG_INTERVIEW@@
 * After logging, offers to update the application's status to the round.
 */
module.exports = async (params) => {
  const { app, quickAddApi } = params;
  const NOTES_FOLDER = "@@DAILY_NOTES_FOLDER@@";
  const HEADING = "@@PREP_HEADING@@";
  const TAG = "@@TAG_INTERVIEW@@";
  const ROUNDS = @@INTERVIEW_ROUNDS_JSON@@;
  const APPS = "@@APPLICATIONS_FOLDER@@/applications.csv";
  const ACTIVE = ["HR Call", "HM Interview", "OA", "Phone Screen", "Onsite", "Team Match"];

  const clean = s => (s || "").replace(/·/g, "-").trim();

  // --- CSV helpers (quote-aware, same conventions as the other scripts) ---
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
    return rows;
  }
  const quote = v => /[",\n\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;

  // --- prompts (Escape anywhere cancels the whole thing) ---
  const iso = d => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); // local date, not UTC
  const today = new Date();
  const yesterday = new Date(today.getTime() - 864e5);
  let day = await quickAddApi.suggester(
    ["Today (" + iso(today) + ")", "Yesterday (" + iso(yesterday) + ")", "Another date…"],
    [iso(today), iso(yesterday), "OTHER"]);
  if (day == null) return;
  while (day === "OTHER") {
    const typed = ((await quickAddApi.inputPrompt(
      "Which day — type as YYYY-MM-DD (e.g. " + iso(yesterday) + ")")) || "").trim();
    if (typed === "") return; // nothing typed: treat as cancel
    if (/^\d{4}-\d{2}-\d{2}$/.test(typed) && !isNaN(new Date(typed + "T12:00:00").getTime())) {
      day = typed;
    } else {
      new Notice("PrepDojo: '" + typed + "' isn't a valid date — use YYYY-MM-DD, e.g. " + iso(today));
    }
  }

  // --- which application? fuzzy over the tracker, manual fallback ---
  let who = "";
  let appRow = null; // CSV row identity, for the optional status update
  if (await app.vault.adapter.exists(APPS)) {
    const rows = parseCSV(await app.vault.adapter.read(APPS));
    const header = rows[0] || [];
    const col = n => header.indexOf(n);
    const get = (r, n) => { const i = col(n); return i >= 0 ? (r[i] ?? "") : ""; };
    if (rows.length > 1) {
      const order = rows.slice(1).map(r => r);
      order.sort((a, b) => {
        const aa = ACTIVE.includes(get(a, "Status").trim()) ? 0 : 1;
        const bb = ACTIVE.includes(get(b, "Status").trim()) ? 0 : 1;
        if (aa !== bb) return aa - bb;
        return get(b, "Applied Date").localeCompare(get(a, "Applied Date"));
      });
      const MANUAL = "✎ Not in my tracker — type it";
      const labels = [MANUAL].concat(order.map(r =>
        get(r, "Company") + " — " + get(r, "Position Title")
        + " · " + (get(r, "Status") || "?")));
      const picked = await quickAddApi.suggester(labels, [null].concat(order));
      if (picked === undefined) return; // Escape
      if (picked !== null) {
        appRow = { company: get(picked, "Company"), position: get(picked, "Position Title") };
        who = clean(appRow.company + " — " + appRow.position);
      }
    }
  }
  if (!who) {
    who = clean(await quickAddApi.inputPrompt(
      "Company — Position (required, e.g. Stripe — ML Engineer)"));
    if (!who) return;
  }

  const round = await quickAddApi.suggester(ROUNDS, ROUNDS);
  if (round == null) return;

  const questions = clean(await quickAddApi.inputPrompt(
    "Questions asked — separate with ; — Enter on empty = leave empty"));
  const reflections = clean(await quickAddApi.inputPrompt(
    "How did it go? What to fix? Enter on empty = leave empty"));

  const entry = "- " + [who, round, questions ? "Q: " + questions : "", reflections]
    .filter(Boolean).join(" · ") + " #" + TAG;

  // --- write into the daily note, under the prep heading ---
  const d = new Date(day + "T12:00:00");
  const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  const months = ["January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December"];
  const fmt = f => f.replace(/dddd/g, days[d.getDay()]).replace(/MMMM/g, months[d.getMonth()])
    .replace(/YYYY/g, d.getFullYear()).replace(/MM/g, String(d.getMonth() + 1).padStart(2, "0"))
    .replace(/DD/g, String(d.getDate()).padStart(2, "0")).replace(/\bD\b/g, d.getDate());
  const path = NOTES_FOLDER + "/" + fmt("@@DATE_FORMAT@@") + ".md";

  let content;
  if (await app.vault.adapter.exists(path)) {
    content = await app.vault.adapter.read(path);
  } else {
    let t;
    try { t = await app.vault.adapter.read("@@DAILY_NOTE_TEMPLATE@@"); }
    catch (e) { t = "# {{date:dddd, MMMM D, YYYY}}\n\n" + HEADING + "\n"; }
    content = t.replace(/\{\{date:([^}]*)\}\}/g, (_, f) => fmt(f))
               .replace(/\{\{date\}\}/g, day);
  }
  const lines = content.split("\n");
  let start = lines.indexOf(HEADING);
  if (start === -1) { lines.push("", HEADING, ""); start = lines.indexOf(HEADING); }
  start += 1;
  let end = start;
  const level = HEADING.split(" ")[0] + " ";
  while (end < lines.length && !lines[end].startsWith(level)) end++;
  for (let i = start; i < end; i++) {
    if (lines[i].trim() === entry.trim()) {
      new Notice("PrepDojo: already logged on " + day);
      return;
    }
  }
  let at = start;
  for (let i = start; i < end; i++) if (lines[i].trim()) at = i + 1;
  if (at === start && (start >= lines.length || lines[start].trim() !== "")) {
    lines.splice(start, 0, ""); at = start + 1;
  }
  lines.splice(at, 0, entry);
  await app.vault.adapter.write(path, lines.join("\n"));
  new Notice("Logged: " + who + " (" + round + ") → " + day);

  // --- optionally sync the application status to this round ---
  if (!appRow || !ACTIVE.includes(round)) return;
  const yes = await quickAddApi.suggester(
    ["Also set the application status to '" + round + "'", "Skip — leave the status as is"],
    [true, false]);
  if (yes !== true) return;
  // Merge into a FRESH read (never write back a stale copy; other writers
  // may have touched the file while the prompts were open).
  const fresh = parseCSV(await app.vault.adapter.read(APPS));
  const fheader = fresh[0] || [];
  const fcol = n => fheader.indexOf(n);
  const fval = (r, n) => { const i = fcol(n); return i >= 0 ? (r[i] ?? "") : ""; };
  const fset = (r, n, v) => {
    const i = fcol(n); if (i < 0) return;
    while (r.length <= i) r.push("");
    r[i] = v;
  };
  const norm = v => (v || "").trim().toLowerCase();
  const target = fresh.slice(1).find(r =>
    norm(fval(r, "Company")) === norm(appRow.company) &&
    norm(fval(r, "Position Title")) === norm(appRow.position));
  if (!target) { new Notice("PrepDojo: application not found in the CSV — status unchanged."); return; }
  if (fval(target, "Status").trim() !== round) {
    fset(target, "Status", round);
    const hist = fval(target, "Stage History").trim();
    fset(target, "Stage History", hist ? hist + " → " + round : round);
  }
  fset(target, "Last Update", iso(today));
  await app.vault.adapter.write(APPS, fresh.map(r => r.map(quote).join(",")).join("\n") + "\n");
  new Notice("Application status: " + round);
};
