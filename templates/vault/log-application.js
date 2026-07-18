/* PrepDojo: quick application logging from inside Obsidian.
 * Generated from config.toml — edit templates/vault/log-application.js in the
 * PrepDojo repo, not this copy. Runs as a QuickAdd macro user script.
 */
module.exports = async (params) => {
  const { app, quickAddApi } = params;
  const FOLDER = "@@APPLICATIONS_FOLDER@@";
  const APPS = FOLDER + "/applications.csv";
  const VERSIONS = FOLDER + "/resume-versions.csv";

  // --- tiny CSV helpers (quote-aware, same conventions as the dashboard) ---
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

  // --- load files ---
  if (!(await app.vault.adapter.exists(APPS))) {
    new Notice("PrepDojo: " + APPS + " not found — run setup first.");
    return;
  }
  const raw = await app.vault.adapter.read(APPS);
  const rows = parseCSV(raw);
  const header = rows[0] || [];
  const col = name => header.indexOf(name);

  let versionIds = [];
  if (await app.vault.adapter.exists(VERSIONS)) {
    const vrows = parseCSV(await app.vault.adapter.read(VERSIONS));
    const idCol = (vrows[0] || []).indexOf("Version ID");
    if (idCol >= 0) versionIds = vrows.slice(1).map(r => r[idCol]).filter(Boolean);
  }

  // --- prompts (Escape anywhere cancels the whole thing) ---
  // Prompt rules, everywhere: Escape cancels the whole log. In optional text
  // prompts, pressing Enter on an empty box leaves that column empty.
  const company = ((await quickAddApi.inputPrompt("Company (required)")) || "").trim();
  if (!company) return;
  const position = ((await quickAddApi.inputPrompt("Position title (required)")) || "").trim();
  if (!position) return;
  const link = await quickAddApi.inputPrompt("Job link — optional: Enter on empty = leave empty");
  if (link == null) return;

  let version = "";
  if (versionIds.length) {
    const NONE = "— leave empty —";
    version = await quickAddApi.suggester([NONE, ...versionIds], ["", ...versionIds]);
    if (version == null) return;
  } else {
    version = ((await quickAddApi.inputPrompt(
      "Resume version — optional: Enter on empty = leave empty")) || "").trim();
  }

  const status = await quickAddApi.suggester(
    ["Applied (submitted it)", "Wishlist (want to apply)"],
    ["Applied", "Wishlist"]);
  if (status == null) return;

  const iso = d => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); // local date, not UTC
  const today = new Date();
  const yesterday = new Date(today.getTime() - 864e5);
  let applied = "";
  if (status === "Applied") {
    applied = await quickAddApi.suggester(
      ["Today (" + iso(today) + ")", "Yesterday (" + iso(yesterday) + ")", "Another date…"],
      [iso(today), iso(yesterday), "OTHER"]);
    if (applied == null) return;
    while (applied === "OTHER") {
      const typed = ((await quickAddApi.inputPrompt(
        "Applied date — type as YYYY-MM-DD (e.g. " + iso(yesterday) + ")")) || "").trim();
      if (typed === "") return; // nothing typed: treat as cancel
      if (/^\d{4}-\d{2}-\d{2}$/.test(typed) && !isNaN(new Date(typed + "T12:00:00").getTime())) {
        applied = typed;
      } else {
        new Notice("PrepDojo: '" + typed + "' isn't a valid date — use YYYY-MM-DD, e.g. " + iso(today));
      }
    }
  }

  // --- dedupe: same company + position already tracked ---
  const cc = col("Company"), cp = col("Position Title");
  for (const r of rows.slice(1)) {
    if ((r[cc] || "").trim().toLowerCase() === company.trim().toLowerCase() &&
        (r[cp] || "").trim().toLowerCase() === position.trim().toLowerCase()) {
      new Notice("PrepDojo: already tracked — " + company + " / " + position);
      return;
    }
  }

  // --- build and append the row ---
  const values = {
    "Company": company, "Position Title": position, "Job Link": link || "",
    "Applied Date": applied, "Resume Version": version,
    "Status": status, "Stage History": status, "Last Update": iso(today),
  };
  const line = header.map(h => quote(values[h] ?? "")).join(",");
  const body = raw.endsWith("\n") || raw === "" ? raw : raw + "\n";
  await app.vault.adapter.write(APPS, body + line + "\n");
  new Notice("Logged: " + company + " — " + position + " (" + status + ")");
};
