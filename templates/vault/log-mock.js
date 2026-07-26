/* PrepDojo: guided mock-interview logging from inside Obsidian.
 * Generated from config.toml — edit templates/vault/log-mock.js in the
 * PrepDojo repo, not this copy. Runs as a QuickAdd macro user script.
 *
 * Entry shape (notes optional, no separator litter when skipped):
 *   - <session> · <type> · <notes> #@@TAG_MOCK@@
 * The dashboard tells fields apart without labels: types come from a closed
 * list, everything after is notes.
 */
module.exports = async (params) => {
  const { app, quickAddApi } = params;
  const FOLDER = "@@DAILY_NOTES_FOLDER@@";
  const HEADING = "@@PREP_HEADING@@";
  const TAG = "@@TAG_MOCK@@";
  const TYPES = @@MOCK_TYPES_JSON@@;

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

  const what = clean(await quickAddApi.inputPrompt(
    "Mock session — who/where? (required, e.g. Pramp with senior eng)"));
  if (!what) return;

  const type = await quickAddApi.suggester(TYPES, TYPES);
  if (type == null) return;

  const notes = clean(await quickAddApi.inputPrompt(
    "Reflections — what went well, what to fix? Enter on empty = leave empty"));

  const entry = "- " + [what, type, notes].filter(Boolean).join(" · ") + " #" + TAG;

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
  new Notice("Logged: " + what + " (" + type + ") → " + day);
};
