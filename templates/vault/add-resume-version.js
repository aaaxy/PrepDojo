/* PrepDojo: add a resume version to the catalog from inside Obsidian.
 * Generated from config.toml — edit templates/vault/add-resume-version.js in
 * the PrepDojo repo, not this copy. Runs as a QuickAdd macro user script.
 */
module.exports = async (params) => {
  const { app, quickAddApi } = params;
  const FILE = "@@APPLICATIONS_FOLDER@@/resume-versions.csv";

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

  if (!(await app.vault.adapter.exists(FILE))) {
    new Notice("PrepDojo: " + FILE + " not found — run setup first.");
    return;
  }
  const raw = await app.vault.adapter.read(FILE);
  const rows = parseCSV(raw);
  const header = rows[0] || [];
  const idCol = header.indexOf("Version ID");
  const existing = rows.slice(1).map(r => (r[idCol] || "").trim()).filter(Boolean);

  // Prompt rules: Escape cancels everything. On optional prompts, Enter on an
  // empty box leaves that column empty.
  let id = "";
  while (!id) {
    id = ((await quickAddApi.inputPrompt(
      "Version ID (required — kebab-case, e.g. llm-agent-v2)")) || "").trim().toLowerCase();
    if (id === "" ) return; // empty or Escape: cancel
    if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(id)) {
      new Notice("PrepDojo: use kebab-case — lowercase letters, digits, hyphens (e.g. fraud-risk-v2)");
      id = "";
    } else if (existing.includes(id)) {
      new Notice("PrepDojo: version '" + id + "' already exists");
      id = "";
    }
  }
  const desc = ((await quickAddApi.inputPrompt("Short description (required)")) || "").trim();
  if (!desc) return;
  const emphasis = await quickAddApi.inputPrompt("Emphasis / angle — what this resume highlights (recommended; used for matching)");
  if (emphasis == null) return;
  const roles = await quickAddApi.inputPrompt("Target role type (recommended; used for matching)");
  if (roles == null) return;
  const fpath = await quickAddApi.inputPrompt("Path to the resume PDF — optional: Enter on empty = leave empty");
  if (fpath == null) return;
  const notes = await quickAddApi.inputPrompt("Notes, e.g. companies that fit — optional: Enter on empty = leave empty");
  if (notes == null) return;

  const d = new Date();
  const today = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0")
    + "-" + String(d.getDate()).padStart(2, "0");
  const values = {
    "Version ID": id, "Short Description": desc,
    "Emphasis / Angle": (emphasis || "").trim(), "Target Role Type": (roles || "").trim(),
    "File Path": (fpath || "").trim(), "Date Last Updated": today,
    "Notes": (notes || "").trim(),
  };
  const line = header.map(h => quote(values[h] ?? "")).join(",");
  const body = raw.endsWith("\n") || raw === "" ? raw : raw + "\n";
  await app.vault.adapter.write(FILE, body + line + "\n");
  new Notice("Added resume version: " + id + " — it's now in the logging dropdown");
};
