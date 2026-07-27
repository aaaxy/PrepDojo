#!/usr/bin/env python3
"""Append one job application to applications.csv, safely.

Usage:
    python3 append_application.py <tracker_folder> <application.json>

<tracker_folder> is the folder holding applications.csv (the `applications`
section of prepdojo.json names it). <application.json> is a JSON object of
snake_case fields (see FIELD_TO_COLUMN below for the full list).

Guarantees, matching PrepDojo's other writers:
- header-keyed: column order in the user's CSV never matters
- quote-aware writing via the csv module — never string-edits a line
- refuses duplicates (same company + req ID, or same company + position title)
- Stage History defaults to the initial status; the script never rewrites
  existing rows
- refuses relative dates: the caller resolves "today" in the USER'S timezone
  from conversation context and passes YYYY-MM-DD. A sandbox clock can be a
  day off for the user, so this script never consults it.
- re-reads the file at write time and appends only — concurrent writers
  (Obsidian buttons, the CLI) are never clobbered

Exit codes: 0 appended, 2 duplicate, 1 anything else (message on stderr).
Never creates the CSV: a missing file means the tracker isn't set up here.
"""

import csv
import io
import json
import re
import sys
from pathlib import Path

FIELD_TO_COLUMN = {
    "company": "Company",
    "position_title": "Position Title",
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
    "stage_history": "Stage History",
    "last_update": "Last Update",
    "next_action": "Next Action",
    "recruiter_contact": "Recruiter / Contact",
    "notes": "Notes",
    "follow_up_date": "Follow-up Date",
}
REQUIRED = ["company", "position_title", "status", "last_update"]
DATE_FIELDS = ["applied_date", "last_update", "follow_up_date"]
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def norm(v):
    return (v or "").strip().lower()


def main():
    if len(sys.argv) != 3:
        die(__doc__)
    folder, payload_path = Path(sys.argv[1]), Path(sys.argv[2])
    apps = folder / "applications.csv"
    if not apps.exists():
        die("%s not found — the tracker isn't set up here; never create it." % apps)

    fields = json.loads(payload_path.read_text(encoding="utf-8"))
    unknown = sorted(set(fields) - set(FIELD_TO_COLUMN))
    if unknown:
        die("Unknown field(s): %s. Known: %s"
            % (", ".join(unknown), ", ".join(sorted(FIELD_TO_COLUMN))))
    missing = [k for k in REQUIRED if not str(fields.get(k, "")).strip()]
    if missing:
        die("Missing required field(s): %s" % ", ".join(missing))
    for k in DATE_FIELDS:
        v = str(fields.get(k, "")).strip()
        if v and not ISO_DATE.match(v):
            die("Field %r must be YYYY-MM-DD (got %r). Resolve relative dates "
                "like 'today' in the user's timezone before calling." % (k, v))

    # ' · ' is PrepDojo's field separator inside note-style cells
    fields = {k: str(v).replace("·", "-").strip() if k == "notes" else str(v).strip()
              for k, v in fields.items()}
    if not fields.get("stage_history"):
        fields["stage_history"] = fields["status"]

    with open(apps, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.reader(f) if any(c.strip() for c in r)]
    if not rows:
        die("%s has no header row." % apps)
    header = rows[0]
    for col in ("Company", "Position Title"):
        if col not in header:
            die("Column %r not found in %s header — is this a PrepDojo tracker?"
                % (col, apps))
    absent = sorted(FIELD_TO_COLUMN[k] for k in fields if FIELD_TO_COLUMN[k] not in header)
    if absent:
        die("Value(s) given for column(s) missing from the CSV header: %s. "
            "Add the column(s) to the header first (see PrepDojo release notes)."
            % ", ".join(absent))

    def get(row, col):
        i = header.index(col)
        return row[i] if i < len(row) else ""

    company, req_id = norm(fields["company"]), norm(fields.get("req_id"))
    title = norm(fields["position_title"])
    for row in rows[1:]:
        same_co = norm(get(row, "Company")) == company
        if same_co and req_id and "Req ID" in header and norm(get(row, "Req ID")) == req_id:
            die("Duplicate: %s / req %s already tracked." % (fields["company"], fields["req_id"]), 2)
        if same_co and norm(get(row, "Position Title")) == title:
            die("Duplicate: %s / %s already tracked." % (fields["company"], fields["position_title"]), 2)

    by_col = {FIELD_TO_COLUMN[k]: v for k, v in fields.items()}
    line = io.StringIO()
    csv.writer(line, lineterminator="\n").writerow([by_col.get(c, "") for c in header])

    # Append-only, with a fresh read of the tail to keep the newline clean.
    current = apps.read_text(encoding="utf-8")
    sep = "" if (current.endswith("\n") or current == "") else "\n"
    with open(apps, "a", newline="", encoding="utf-8") as f:
        f.write(sep + line.getvalue())
    print("Appended: %s — %s (%s)"
          % (fields["company"], fields["position_title"], fields["status"]))


if __name__ == "__main__":
    main()
