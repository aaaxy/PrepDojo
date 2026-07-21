/* PrepDojo: update an existing application from inside Obsidian.
 * Generated from config.toml — edit templates/vault/update-application.js in
 * the PrepDojo repo, not this copy. Runs as a QuickAdd macro user script.
 *
 * Flow: fuzzy-find the application (type any fragment of company/position),
 * then update fields one by one; nothing is written until "Save & finish".
 * Escape at any prompt discards all pending changes.
 */
module.exports = async (params) => {
  const { app, quickAddApi } = params;
  const FOLDER = "@@APPLICATIONS_FOLDER@@";
  const APPS = FOLDER + "/applications.csv";

  const STATUSES = ["Applied", "HR Call", "OA", "Phone Screen", "Onsite",
    "Team Match", "Offer", "Rejected", "Withdrawn", "Wishlist"];
  const ACTIVE = ["HR Call", "OA", "Phone Screen", "Onsite", "Team Match"];

  // --- CSV helpers (quote-aware, same conventions as the dashboard) ---
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

  if (!(await app.vault.adapter.exists(APPS))) {
    new Notice("PrepDojo: " + APPS + " not found — run setup first.");
    return;
  }
  const rows = parseCSV(await app.vault.adapter.read(APPS));
  const header = rows[0] || [];
  const col = name => header.indexOf(name);
  const get = (r, name) => { const i = col(name); return i >= 0 ? (r[i] ?? "") : ""; };
  const set = (r, name, v) => {
    const i = col(name); if (i < 0) return;
    while (r.length <= i) r.push("");
    r[i] = v;
  };
  if (rows.length < 2) { new Notice("PrepDojo: no applications logged yet."); return; }

  // --- pick the application: fuzzy search over all rows ---
  // Active applications first, then most recently applied.
  const order = rows.slice(1).map((r, i) => ({ r, i: i + 1 }));
  order.sort((a, b) => {
    const aa = ACTIVE.includes(get(a.r, "Status").trim()) ? 0 : 1;
    const bb = ACTIVE.includes(get(b.r, "Status").trim()) ? 0 : 1;
    if (aa !== bb) return aa - bb;
    return get(b.r, "Applied Date").localeCompare(get(a.r, "Applied Date"));
  });
  const labels = order.map(o =>
    get(o.r, "Company") + " — " + get(o.r, "Position Title")
    + " · " + (get(o.r, "Status") || "?")
    + (get(o.r, "Applied Date") ? " · applied " + get(o.r, "Applied Date") : ""));
  const pickIdx = await quickAddApi.suggester(labels, order.map(o => o.i));
  if (pickIdx == null) return;
  const row = rows[pickIdx];
  const who = get(row, "Company") + " — " + get(row, "Position Title");
  // Identity of the picked row + the columns actually edited, so the save can
  // merge into a fresh read instead of writing back this (possibly stale) copy.
  const origCompany = get(row, "Company"), origPosition = get(row, "Position Title");
  const touched = new Set();

  // --- date helpers ---
  const iso = d => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); // local date, not UTC
  const today = new Date();
  const plus = n => { const d = new Date(today.getTime() + n * 864e5); return iso(d); };

  // --- update loop: collect changes, write once at the end ---
  let changes = 0;
  while (true) {
    const menu = [
      "✓ Save & finish" + (changes ? " (" + changes + " change" + (changes === 1 ? "" : "s") + ")" : ""),
      "Status (now: " + (get(row, "Status") || "—") + ")",
      "Add a note",
      "Recruiter / Contact (now: " + (get(row, "Recruiter / Contact") || "—") + ")",
      "Follow-up date (now: " + (get(row, "Follow-up Date") || "—") + ")",
      "Comp Range (now: " + (get(row, "Comp Range") || "—") + ")",
      "Next Action (now: " + (get(row, "Next Action") || "—") + ")",
    ];
    const action = await quickAddApi.suggester(menu,
      ["done", "status", "note", "contact", "followup", "comp", "next"]);
    if (action == null) {
      if (changes) new Notice("PrepDojo: discarded " + changes + " unsaved change(s).");
      return;
    }
    if (action === "done") break;

    if (action === "status") {
      const cur = get(row, "Status").trim();
      const s = await quickAddApi.suggester(
        STATUSES.map(x => x === cur ? x + " (current)" : x), STATUSES);
      if (s == null || s === cur) continue;
      set(row, "Status", s);
      const hist = get(row, "Stage History").trim();
      set(row, "Stage History", hist ? hist + " → " + s : s);
      touched.add("Status"); touched.add("Stage History");
      changes++;
    } else if (action === "note") {
      const n = ((await quickAddApi.inputPrompt("Note (dated automatically)")) || "").trim();
      if (!n) continue;
      const cur = get(row, "Notes").trim();
      const stamped = iso(today) + ": " + n.replace(/·/g, "-");
      set(row, "Notes", cur ? cur + " | " + stamped : stamped);
      touched.add("Notes");
      changes++;
    } else if (action === "contact") {
      const c = await quickAddApi.inputPrompt(
        "Recruiter / contact (name, email…)", "", get(row, "Recruiter / Contact"));
      if (c == null) continue;
      set(row, "Recruiter / Contact", c.trim());
      touched.add("Recruiter / Contact");
      changes++;
    } else if (action === "followup") {
      const f = await quickAddApi.suggester(
        ["Tomorrow (" + plus(1) + ")", "In 3 days (" + plus(3) + ")",
         "In a week (" + plus(7) + ")", "Another date…", "Clear"],
        [plus(1), plus(3), plus(7), "OTHER", ""]);
      if (f == null) continue;
      let v = f;
      while (v === "OTHER") {
        const typed = ((await quickAddApi.inputPrompt(
          "Follow-up date — type as YYYY-MM-DD")) || "").trim();
        if (typed === "") { v = null; break; }
        if (/^\d{4}-\d{2}-\d{2}$/.test(typed) && !isNaN(new Date(typed + "T12:00:00").getTime())) v = typed;
        else new Notice("PrepDojo: '" + typed + "' isn't a valid date — use YYYY-MM-DD.");
      }
      if (v == null) continue;
      set(row, "Follow-up Date", v);
      touched.add("Follow-up Date");
      changes++;
    } else if (action === "comp") {
      const c = await quickAddApi.inputPrompt("Comp range / offer", "", get(row, "Comp Range"));
      if (c == null) continue;
      set(row, "Comp Range", c.trim());
      touched.add("Comp Range");
      changes++;
    } else if (action === "next") {
      const c = await quickAddApi.inputPrompt("Next action", "", get(row, "Next Action"));
      if (c == null) continue;
      set(row, "Next Action", c.trim());
      touched.add("Next Action");
      changes++;
    }
  }

  if (!changes) { new Notice("PrepDojo: nothing changed."); return; }
  set(row, "Last Update", iso(today));
  touched.add("Last Update");

  // Merge into a FRESH read of the file. Writing back the copy read at the
  // start would erase anything logged by other writers (AI skill, spreadsheet,
  // ＋ Application) while the prompts were open.
  const fresh = parseCSV(await app.vault.adapter.read(APPS));
  const fheader = fresh[0] || [];
  const fcol = n => fheader.indexOf(n);
  const fval = (r, n) => { const i = fcol(n); return i >= 0 ? (r[i] ?? "") : ""; };
  const norm = v => (v || "").trim().toLowerCase();
  const target = fresh.slice(1).find(r =>
    norm(fval(r, "Company")) === norm(origCompany) &&
    norm(fval(r, "Position Title")) === norm(origPosition));
  if (!target) {
    new Notice("PrepDojo: " + who + " is no longer in the CSV (changed while you edited?) — nothing written.");
    return;
  }
  for (const name of touched) {
    const i = fcol(name);
    if (i < 0) continue;
    while (target.length <= i) target.push("");
    target[i] = get(row, name);
  }
  const out = fresh.map(r => r.map(quote).join(",")).join("\n") + "\n";
  await app.vault.adapter.write(APPS, out);
  new Notice("Updated " + who + " (" + changes + " change" + (changes === 1 ? "" : "s") + ")");
};
