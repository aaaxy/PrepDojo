---
name: prepdojo-applications
description: Log and update job applications in the user's PrepDojo tracker (CSV files inside their Obsidian vault, read live by a Dataview dashboard). Trigger when the user says things like "log this application", "I applied to X", "add this to my tracker", or reports a stage change — "X moved me to phone screen", "got rejected by Y", "offer from Z", "recruiter reached out". Also trigger for follow-up bookkeeping ("remind me to follow up with X on Friday" → set the row's follow-up date). Do NOT trigger for resume advice, cover letters, or interview prep questions.
---

# PrepDojo Applications

Log new job applications and record stage changes in the user's application tracker: `applications.csv` (one row per application) and `resume-versions.csv` (the resume catalog), living in a folder inside their Obsidian vault. A Dataview dashboard computes pipeline stats live from these files — writing the row is all it takes; never edit the dashboard.

The tracker is the user's source of truth for a high-stakes job search. Two consequences, always:

- **Preview before writing.** Show the row or the change you intend to write and get an explicit yes. Never auto-log.
- **The scripts do the writing.** Use the bundled scripts for every write — they are quote-aware, header-keyed, dedupe-checked, and append-only where it matters. Never string-edit a CSV line, and never rewrite the files by hand.

## Find the tracker (once per session)

All paths come from `prepdojo.json` at the user's vault root, written by PrepDojo's `generate.py`. Locate it ONCE per session, in this order, stopping at the first success:

1. **Pointer file.** Read `~/.claude/prepdojo-vault.json` (shape: `{"vault_path": "..."}`). If `<vault_path>/prepdojo.json` exists and parses, use it.
2. **Working folder.** Check the current working folder for `prepdojo.json`, then each parent up to three levels.
3. **Shallow search.** Search the session's accessible folders (connected/mounted folders, uploaded folders) for `prepdojo.json`, depth-limited (e.g. `find <root> -maxdepth 3 -name prepdojo.json -not -path '*/.*'`). Exactly one hit: use it silently. Several: ask which vault.
4. **Ask.** If nothing is found, ask the user where their vault is — they may need to connect the folder. Never guess, and never create `prepdojo.json` or the CSVs yourself.

After locating via steps 2–4, write the pointer file (create `~/.claude/` if needed) so future sessions skip the search; if the write fails, continue without it.

The tracker folder is `<vault>/<config.applications.folder>`; the CSV filenames and column schemas are in the `applications` section of `prepdojo.json`. If the vault is mounted read-only in this environment (e.g. a staged copy), run the scripts on a writable copy and write the result back through the platform's write-back mechanism.

## Dates

Every date passed to the scripts is a literal `YYYY-MM-DD`, resolved by YOU in the user's timezone from the conversation context (the host injects the user's current date). Never run `date` in a sandboxed shell and never let the scripts consult a clock — a sandbox on UTC rolls to the next calendar day mid-evening for many users and would silently mis-date rows. The scripts enforce this by rejecting anything that isn't `YYYY-MM-DD`. If the user names another day ("I applied last Friday"), resolve that instead. If the context gives no date, ask.

## Logging a new application

1. Gather fields from what the user gave (a URL, pasted JD text, or a plain sentence). If they shared a posting URL, a web fetch may fill in company, title, location, remote status, comp range, and a Req ID; if fetching fails (LinkedIn, many Workday instances), ask for the key fields instead of guessing.
2. If `resume-versions.csv` exists and has entries, offer its Version IDs (read-only; parse with a proper CSV reader) when the user hasn't named a resume version. Leave the field empty rather than inventing a version.
3. Default status to `Wishlist` unless the user says they already applied (then `Applied`, with `applied_date` set). Always set `last_update`. Leave unknown fields empty — no placeholder text.
4. Preview the row (company, title, req ID, location, resume version, status) and ask to confirm.
5. On yes, write the fields as JSON to a temp file and run:

```bash
python3 <skill>/scripts/append_application.py "<tracker-folder>" <application.json>
```

Field keys: `company`, `position_title`, `req_id`, `job_link`, `location`, `remote`, `comp_range`, `applied_date`, `resume_version`, `cover_letter`, `referral`, `status`, `stage_history`, `last_update`, `next_action`, `recruiter_contact`, `notes`, `follow_up_date`. Omit `stage_history` — the script defaults it to the initial status. The script refuses duplicates (same company + req ID, or same company + position title): if it reports one, tell the user instead of forcing the write.

6. Confirm in one line. Don't recap the whole row — the user just previewed it.

## Updating an existing application

For stage changes ("Stripe moved me to phone screen"), follow-ups, recruiter contacts, comp updates, or dated notes:

1. Preview the change ("Stripe — ML Engineer: Status → Phone Screen, follow-up 2026-07-30") and get a yes.
2. Write the update as JSON to a temp file and run:

```bash
python3 <skill>/scripts/update_application.py "<tracker-folder>" <update.json>
```

The JSON carries `company`, `position_title`, `last_update`, plus any of: `set` (fields to replace — `status`, `next_action`, `follow_up_date`, `recruiter_contact`, `comp_range`, ...), `stage_note` (annotates a status change, e.g. "R1: ML domain + BQ, Jul 26"), `append_note` (a dated note appended to Notes). The script finds the row fresh at call time, appends status changes to Stage History (never rewrites it — `set.stage_history` is refused), and preserves existing notes.

If the script reports no row or several rows, relay that to the user — never "fix" it by editing the CSV directly.

## Special situations

- **Tracker not found** (no `prepdojo.json`, or the CSVs missing from the applications folder): ask the user — their setup may have moved. Never create CSV files; PrepDojo's installer owns their creation.
- **"Log this" with no details**: ask for the URL or the key fields. Don't guess.
- **Schema drift** (script errors about a column missing from the header): the user's CSV predates a schema addition — tell them which column to append to their header row, per PrepDojo's release notes. Don't add it yourself without their yes.
- **Which resume fits this posting?** This skill tracks applications; it doesn't rank resumes. If the user has their own resume-matching setup, defer to it; otherwise compare the `resume-versions.csv` descriptions honestly and say when nothing fits.
