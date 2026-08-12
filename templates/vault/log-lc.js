/* PrepDojo: guided LeetCode-style logging from inside Obsidian.
 * Generated from config.toml — edit templates/vault/log-lc.js in the
 * PrepDojo repo, not this copy. Runs as a QuickAdd macro user script.
 *
 * Entry shape (topic is optional; without it the dashboard lists the entry
 * under "Needs topic"):
 *   - LC <problem> · <difficulty> · <topic> #@@TAG_LC@@
 * The topic picker offers the configured topics plus every topic already
 * used in your log, and "＋ New topic…" for typing a brand-new one.
 */
module.exports = async (params) => {
  const { app, quickAddApi } = params;
  const FOLDER = "@@DAILY_NOTES_FOLDER@@";
  const HEADING = "@@PREP_HEADING@@";
  const TAG = "@@TAG_LC@@";
  const DIFFICULTIES = "@@DIFFICULTIES_CSV@@".split(",");
  const TOPICS = "@@TOPICS_CSV@@".split(",");

  // "·" is the field separator, so it can't appear inside a field
  const clean = s => (s || "").replace(/·/g, "-").trim();

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

  const problem = clean(await quickAddApi.inputPrompt(
    "Problem name (required, e.g. #200 Number of Islands)"));
  if (!problem) return;

  const diff = await quickAddApi.suggester(DIFFICULTIES, DIFFICULTIES);
  if (diff == null) return;

  // --- topic: configured list ∪ topics already used in the log ---
  // Anything you ever typed as a topic keeps showing up here, so new topics
  // are remembered without any config edit.
  const known = new Set(TOPICS.map(t => t.toLowerCase()));
  const used = new Set();
  const tagRe = new RegExp("#" + TAG + "\\b");
  for (const f of app.vault.getMarkdownFiles()) {
    if (!f.path.startsWith(FOLDER + "/")) continue;
    let text;
    try { text = await app.vault.cachedRead(f); } catch (e) { continue; }
    if (!tagRe.test(text)) continue;
    for (const line of text.split("\n")) {
      if (!tagRe.test(line) || !line.trim().startsWith("-")) continue;
      const body = line.replace(/^\s*-\s*(\[.\]\s*)?/, "").replace(tagRe, "")
        .replace(/^LC\s*/i, "").trim();
      const parts = body.split("·").map(s => s.trim());
      const t = (parts[2] || "").toLowerCase();
      if (t && t !== "—" && !known.has(t)) used.add(t);
    }
  }
  const options = TOPICS.concat([...used].sort());
  const NEW = "＋ New topic…", SKIP = "— skip for now —";
  const pick = await quickAddApi.suggester(
    [SKIP, NEW, ...options], ["", "NEW", ...options]);
  if (pick == null) return;
  let topic = pick;
  if (pick === "NEW") {
    topic = clean(await quickAddApi.inputPrompt(
      "New topic (e.g. union find, or dp - knapsack to count under dp)"));
  }

  const entry = "- LC " + [problem, diff, topic].filter(Boolean).join(" · ")
    + " #" + TAG;

  // --- write into the daily note, under the prep heading ---
  const d = new Date(day + "T12:00:00");
  const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  const months = ["January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December"];
  const fmt = f => f.replace(/dddd/g, days[d.getDay()]).replace(/MMMM/g, months[d.getMonth()])
    .replace(/YYYY/g, d.getFullYear()).replace(/MM/g, String(d.getMonth() + 1).padStart(2, "0"))
    .replace(/DD/g, String(d.getDate()).padStart(2, "0")).replace(/\bD\b/g, d.getDate());
  const path = FOLDER + "/" + fmt("@@DATE_FORMAT@@") + ".md";

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
      new Notice("PrepDojo: already logged on " + day
        + " — repeats on other days are counted automatically.");
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
  new Notice("Logged: " + problem + " (" + diff + (topic ? ", " + topic : "") + ") → " + day);
};
