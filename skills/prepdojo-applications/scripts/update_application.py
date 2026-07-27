#!/usr/bin/env python3
"""Update one existing row of applications.csv, safely.

Usage:
    python3 update_application.py <tracker_folder> <update.json>

<update.json> shape:
    {
      "company": "Stripe",                  # required, matched case-insensitively
      "position_title": "ML Engineer",      # required, matched case-insensitively
      "last_update": "2026-07-26",          # required, YYYY-MM-DD, user's local date
      "set": {"status": "Phone Screen",     # optional: snake_case fields to replace
              "next_action": "..."},        #   (stage_history NOT allowed here)
      "stage_note": "R1: ML + BQ, Jul 26",  # optional: annotates a status change
      "append_note": "recruiter pinged"     # optional: dated, appended to Notes
    }

Guarantees, matching PrepDojo's other writers:
- header-keyed, quote-aware via the csv module — never string-edits a line
- reads the file FRESH at call time; finds the row by company + position title
  (rerun after a rename — this script never guesses)
- Stage History is append-only: a status change appends " → <new> (<note>)",
  history is never rewritten (that's why "set" refuses stage_history)
- notes are appended with a date stamp, existing notes preserved
- refuses relative dates: the caller resolves "today" in the USER'S timezone
  from conversation context and passes YYYY-MM-DD

Exit codes: 0 updated, 2 row not found, 3 several rows match, 1 anything else.
"""

import csv
import json
import re
import sys
from pathlib import Path

SETTABLE = {
    "req_id": "Req ID",
    "job_link": "Job Link",
    "location": "Location",
    "remote": "Remote?",
    "comp_range": "Comp Range",
    "applied_date": "Applied Date",
    "resume_version": "Resume Version",
    "cover_letter": "Cover Letter",
    "referral": "Referral",
    "status": "Status",
    "next_action": "Next Action",
    "recruiter_contact": "Recruiter / Contact",
    "follow_up_date": "Follow-up Date",
}
DATE_FIELDS = {"applied_date", "follow_up_date"}
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def norm(v):
    return (v or "").strip().lower()


def clean(v):
    # ' · ' is PrepDojo's field separator convention; keep it out of cells
    return str(v).replace("·", "-").strip()


def main():
    if len(sys.argv) != 3:
        die(__doc__)
    folder, payload_path = Path(sys.argv[1]), Path(sys.argv[2])
    apps = folder / "applications.csv"
    if not apps.exists():
        die("%s not found — the tracker isn't set up here." % apps)

    upd = json.loads(payload_path.read_text(encoding="utf-8"))
    for k in ("company", "position_title", "last_update"):
        if not str(upd.get(k, "")).strip():
            die("Missing required field: %s" % k)
    if not ISO_DATE.match(upd["last_update"].strip()):
        die("last_update must be YYYY-MM-DD (the user's local date, resolved "
            "from conversation context — never from a sandbox clock).")
    to_set = dict(upd.get("set") or {})
    if "stage_history" in to_set:
        die("Stage History is append-only — change 'status' (optionally with "
            "'stage_note') and the history line is extended automatically.")
    unknown = sorted(set(to_set) - set(SETTABLE))
    if unknown:
        die("Unknown field(s) in 'set': %s. Settable: %s"
            % (", ".join(unknown), ", ".join(sorted(SETTABLE))))
    for k in DATE_FIELDS & set(to_set):
        v = str(to_set[k]).strip()
        if v and not ISO_DATE.match(v):
            die("Field %r must be YYYY-MM-DD (got %r)." % (k, v))
    if not to_set and not upd.get("append_note"):
        die("Nothing to do: give 'set' fields and/or 'append_note'.")

    # Fresh read at call time — other writers may have touched the file.
    with open(apps, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.reader(f) if any(c.strip() for c in r)]
    if not rows:
        die("%s has no header row." % apps)
    header = rows[0]

    def idx(col):
        try:
            return header.index(col)
        except ValueError:
            die("Column %r not found in %s header." % (col, apps))

    def get(row, col):
        i = idx(col)
        return row[i] if i < len(row) else ""

    def put(row, col, val):
        i = idx(col)
        while len(row) <= i:
            row.append("")
        row[i] = val

    matches = [r for r in rows[1:]
               if norm(get(r, "Company")) == norm(upd["company"])
               and norm(get(r, "Position Title")) == norm(upd["position_title"])]
    if not matches:
        die("No row for %s / %s — check applications.csv for the exact names."
            % (upd["company"], upd["position_title"]), 2)
    if len(matches) > 1:
        die("%d rows match %s / %s — disambiguate in the CSV first."
            % (len(matches), upd["company"], upd["position_title"]), 3)
    row = matches[0]

    changed = []
    for k, v in to_set.items():
        col, val = SETTABLE[k], clean(v)
        if k == "status" and val != get(row, "Status").strip():
            hist = get(row, "Stage History").strip()
            step = val + (" (%s)" % clean(upd["stage_note"]) if upd.get("stage_note") else "")
            put(row, "Stage History", (hist + " → " + step) if hist else step)
            changed.append("Stage History")
        if get(row, col) != val:
            put(row, col, val)
            changed.append(col)
    if upd.get("append_note"):
        stamped = upd["last_update"].strip() + ": " + clean(upd["append_note"])
        cur = get(row, "Notes").strip()
        put(row, "Notes", (cur + " | " + stamped) if cur else stamped)
        changed.append("Notes")
    if not changed:
        print("No change: every given value already matches.")
        return
    put(row, "Last Update", upd["last_update"].strip())

    with open(apps, "w", newline="", encoding="utf-8") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    print("Updated %s — %s: %s"
          % (upd["company"], upd["position_title"], ", ".join(dict.fromkeys(changed))))


if __name__ == "__main__":
    main()
