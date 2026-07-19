#!/usr/bin/env python3
"""prepdojo CLI: log daily practice entries into your Obsidian vault.

Examples:
    python3 prepdojo.py log lc "#200 Number of Islands" -d medium -t bfs/dfs
    python3 prepdojo.py log lc "#322 Coin Change" -d M -t dp --note "needed hints" --date yesterday
    python3 prepdojo.py log mlfund "batch norm" --conf yellow
    python3 prepdojo.py log bq "conflict with PM story"
    python3 prepdojo.py streak
    python3 prepdojo.py topics
    python3 prepdojo.py apps log "Stripe" "ML Engineer, Risk" -r fraud-risk --status Applied
    python3 prepdojo.py apps log "OpenAI" "Research Engineer" -r llm-agent --link https://... --date yesterday
    python3 prepdojo.py apps stats

The vault location is resolved in this order:
    1. --vault flag
    2. PREPDOJO_VAULT environment variable
    3. `path` under [vault] in config.toml

Writes plain markdown only; Obsidian does not need to be running.
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import os
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # Python < 3.11 fallback
    except ModuleNotFoundError:
        sys.exit("On Python older than 3.11, install the TOML parser: pip install tomli")

ROOT = Path(__file__).parent

CONFIDENCE = {"green": "\U0001f7e2", "yellow": "\U0001f7e1", "red": "\U0001f534"}

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def load_config() -> dict:
    cfg_path = ROOT / "config.toml"
    template = ROOT / "config-template.toml"
    if not cfg_path.exists():
        if not template.exists():
            sys.exit("No config found. Expected config.toml or config-template.toml "
                     "next to prepdojo.py.")
        # First run: bootstrap a personal, gitignored config from the template.
        cfg_path.write_bytes(template.read_bytes())
        print("Created config.toml from config-template.toml — edit it to customize.")
    with open(cfg_path, "rb") as f:
        return tomllib.load(f)


def resolve_vault(args, cfg) -> Path:
    candidate = args.vault or os.environ.get("PREPDOJO_VAULT") or cfg["vault"].get("path")
    if not candidate:
        sys.exit(
            "No vault location set. Use --vault, set PREPDOJO_VAULT, or add\n"
            '    path = "/absolute/path/to/YourVault"\n'
            "under [vault] in config.toml"
        )
    vault = Path(candidate).expanduser()
    if not vault.is_dir():
        sys.exit(f"Vault directory not found: {vault}")
    return vault


def resolve_date(spec: str) -> dt.date:
    today = dt.date.today()
    s = (spec or "today").strip().lower()
    if s in ("today", "t"):
        return today
    if s in ("yesterday", "yd"):
        return today - dt.timedelta(days=1)
    if s in WEEKDAYS or s.startswith("last "):
        name = s.removeprefix("last ").strip()
        if name in WEEKDAYS:
            delta = (today.weekday() - WEEKDAYS.index(name)) % 7 or 7
            return today - dt.timedelta(days=delta)
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        sys.exit(f"Cannot parse date '{spec}'. Use today, yesterday, a weekday, or YYYY-MM-DD.")


def moment_to_strftime(fmt: str) -> str:
    """Translate the moment.js tokens this project uses into strftime."""
    out, mapping = fmt, {
        "dddd": "%A", "MMMM": "%B", "YYYY": "%Y", "MM": "%m", "DD": "%d",
    }
    for token, strf in mapping.items():
        out = out.replace(token, strf)
    # Bare D (day of month, no leading zero) — handle after longer tokens
    out = re.sub(r"(?<!%)\bD\b", "%-d" if os.name != "nt" else "%#d", out)
    return out


def daily_note_path(vault: Path, cfg: dict, date: dt.date) -> Path:
    folder = vault / cfg["vault"]["daily_notes_folder"]
    fname = date.strftime(moment_to_strftime(cfg["vault"]["date_format"])) + ".md"
    return folder / fname


def render_template(cfg: dict, vault: Path, date: dt.date) -> str:
    tmpl_path = vault / cfg["vault"]["daily_note_template"]
    if tmpl_path.exists():
        text = tmpl_path.read_text(encoding="utf-8")
    else:
        text = f"# {{{{date:dddd, MMMM D, YYYY}}}}\n\n{cfg['vault']['prep_heading']}\n"

    def repl(m):
        fmt = m.group(1)
        if fmt is None:
            return date.isoformat()
        return date.strftime(moment_to_strftime(fmt))

    return re.sub(r"\{\{date(?::([^}]*))?\}\}", repl, text)


def normalize_difficulty(raw: str, difficulties: list[str]) -> str:
    if not raw:
        return ""
    for d in difficulties:
        if raw.lower() in (d.lower(), d[0].lower()):
            return d
    sys.exit(f"Unknown difficulty '{raw}'. Expected one of: "
             + ", ".join(difficulties) + " (or initials)")


def normalize_topic(raw: str, topics: list[str]) -> str:
    if not raw:
        return ""
    t = raw.strip().lower()
    main = t.split(" - ")[0].strip()
    if main in topics:
        return t
    close = difflib.get_close_matches(main, topics, n=3, cutoff=0.5)
    hint = f" Did you mean: {', '.join(close)}?" if close else ""
    sys.exit(f"Unknown topic '{main}'.{hint}\n"
             f"(taxonomy: {', '.join(topics)}; finer divisions like 'dp - knapsack' are fine)")


def build_entry(args, cfg) -> str:
    cat = cfg["categories"][args.category]
    tag = cat["tag"]
    text = args.text.strip()
    if args.category == "lc":
        diff = normalize_difficulty(args.difficulty, cfg["leetcode"]["difficulties"])
        topic = normalize_topic(args.topic, cfg["leetcode"]["topics"])
        if not diff or not topic:
            sys.exit("LeetCode entries need -d/--difficulty and -t/--topic")
        parts = [f"LC {text}", diff, topic]
        if args.note:
            parts.append(args.note.strip())
        return "- " + " · ".join(parts) + f" #{tag}"
    if args.category == "mlfund":
        conf = CONFIDENCE[args.conf]
        return f"- {text} · {conf} #{tag}"
    entry = f"- {text}"
    if args.note:
        entry += f" · {args.note.strip()}"
    return entry + f" #{tag}"


def problem_key(text: str) -> str | None:
    """A LeetCode problem number like '#200' or '200.', for dedupe."""
    m = re.search(r"#\s*(\d+)|\b(\d+)\.", text)
    return (m.group(1) or m.group(2)) if m else None


def insert_entry(note_path: Path, cfg: dict, entry: str, vault: Path, date: dt.date) -> str:
    heading = cfg["vault"]["prep_heading"]
    if note_path.exists():
        content = note_path.read_text(encoding="utf-8")
    else:
        content = render_template(cfg, vault, date)

    lines = content.splitlines()
    if heading not in lines:
        lines += ["", heading, ""]

    # find section bounds
    start = lines.index(heading) + 1
    end = start
    level = heading.split(" ")[0] + " "
    while end < len(lines) and not lines[end].startswith(level):
        end += 1

    section = lines[start:end]
    key = problem_key(entry)
    tag = entry.rsplit("#", 1)[1]
    for line in section:
        if line.strip() == entry.strip():
            return "duplicate"
        if key and f"#{tag}" in line and problem_key(line) == key:
            return "duplicate"

    # insert after the last non-empty line of the section (or right after heading)
    insert_at = start
    for i in range(start, end):
        if lines[i].strip():
            insert_at = i + 1
    if insert_at == start and (start >= len(lines) or lines[start].strip() != ""):
        lines.insert(start, "")
        insert_at = start + 1
    lines.insert(insert_at, entry)

    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return "written"


def cmd_log(args, cfg) -> None:
    if args.category not in cfg["categories"]:
        sys.exit(f"Unknown category '{args.category}'. "
                 f"Available: {', '.join(cfg['categories'])}")
    vault = resolve_vault(args, cfg)
    date = resolve_date(args.date)
    entry = build_entry(args, cfg)
    note = daily_note_path(vault, cfg, date)
    result = insert_entry(note, cfg, entry, vault, date)
    pretty = entry.removeprefix("- ").rsplit(" #", 1)[0]
    if result == "duplicate":
        print(f"Already logged on {date.isoformat()}: {pretty}")
    else:
        print(f"Logged: {pretty} → {date.isoformat()}")


def logged_lines(text: str, tags: list[str]) -> list[str]:
    """Plain bullets or checked tasks carrying one of our tags."""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("- "):
            continue
        if s.startswith("- [ ]"):
            continue  # unchecked placeholder
        if any(f"#{t}" in s for t in tags):
            out.append(s)
    return out


def cmd_streak(args, cfg) -> None:
    vault = resolve_vault(args, cfg)
    folder = vault / cfg["vault"]["daily_notes_folder"]
    tags = {k: c["tag"] for k, c in cfg["categories"].items()}
    names = {k: c["name"] for k, c in cfg["categories"].items()}
    today = dt.date.today()
    week_ago = today - dt.timedelta(days=6)

    total = dict.fromkeys(tags, 0)
    week = dict.fromkeys(tags, 0)
    active: set[dt.date] = set()

    for f in sorted(folder.glob("*.md")):
        try:
            day = dt.date.fromisoformat(f.stem)
        except ValueError:
            continue
        text = f.read_text(encoding="utf-8")
        for key, tag in tags.items():
            n = len(logged_lines(text, [tag]))
            if n:
                total[key] += n
                active.add(day)
                if week_ago <= day <= today:
                    week[key] += n

    streak, d = 0, today if today in active else today - dt.timedelta(days=1)
    while d in active:
        streak += 1
        d -= dt.timedelta(days=1)

    print(f"\U0001f525 Streak: {streak} day{'s' if streak != 1 else ''} "
          f"· active days total: {len(active)}")
    width = max(len(n) for n in names.values())
    print(f"{'Category'.ljust(width)}  7d  all")
    for key in tags:
        print(f"{names[key].ljust(width)}  {week[key]:>2}  {total[key]:>3}")


def cmd_topics(_args, cfg) -> None:
    for t in cfg["leetcode"]["topics"]:
        print(t)


# --- job application tracking (CSV-based) ---------------------------------

APP_STATUSES = ["Wishlist", "Applied", "OA", "Phone Screen", "Onsite",
                "Team Match", "Offer", "Rejected", "Ghosted", "Withdrawn"]

APP_HEADER = ["Company", "Position Title", "Req ID", "Job Link", "Location",
              "Remote?", "Comp Range", "Applied Date", "Resume Version",
              "Cover Letter", "Referral", "Status", "Stage History",
              "Last Update", "Next Action", "Recruiter / Contact", "Notes"]


def apps_folder(vault: Path, cfg: dict) -> Path:
    rel = cfg.get("applications", {}).get("folder", "Career/Job Hunting/NG/Applications")
    return vault / rel


def read_applications(folder: Path) -> tuple[list[str], list[dict]]:
    import csv
    path = folder / "applications.csv"
    if not path.exists():
        return APP_HEADER, []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader
                if any((v or "").strip() for v in r.values())]
        return list(reader.fieldnames or APP_HEADER), rows


def validate_resume_version(raw: str, folder: Path) -> str:
    """Check against resume-versions.csv when it exists; suggest close matches."""
    import csv
    path = folder / "resume-versions.csv"
    if not raw or not path.exists():
        return raw
    with open(path, newline="", encoding="utf-8") as f:
        ids = [r["Version ID"].strip() for r in csv.DictReader(f)
               if (r.get("Version ID") or "").strip()]
    if raw in ids:
        return raw
    close = difflib.get_close_matches(raw, ids, n=3, cutoff=0.4)
    hint = f" Did you mean: {', '.join(close)}?" if close else ""
    sys.exit(f"Unknown resume version '{raw}'.{hint}")


def cmd_apps_log(args, cfg) -> None:
    import csv
    vault = resolve_vault(args, cfg)
    folder = apps_folder(vault, cfg)
    path = folder / "applications.csv"

    status = next((s for s in APP_STATUSES if s.lower() == args.status.lower()), None)
    if not status:
        sys.exit(f"Unknown status '{args.status}'. One of: {', '.join(APP_STATUSES)}")
    resume = validate_resume_version(args.resume, folder)
    applied = resolve_date(args.date).isoformat() if status != "Wishlist" else ""
    today = dt.date.today().isoformat()

    header, existing = read_applications(folder)

    # dedupe: same company + req id, or same company + title when no req id
    for i, r in enumerate(existing, start=2):
        same_co = (r.get("Company") or "").strip().lower() == args.company.strip().lower()
        same_req = args.req_id and (r.get("Req ID") or "").strip().lower() == args.req_id.strip().lower()
        same_title = not args.req_id and \
            (r.get("Position Title") or "").strip().lower() == args.position.strip().lower()
        if same_co and (same_req or same_title):
            sys.exit(f"Already tracked (row {i}): {r.get('Company')} / "
                     f"{r.get('Position Title')} — status: {r.get('Status')}")

    row = {
        "Company": args.company, "Position Title": args.position,
        "Req ID": args.req_id, "Job Link": args.link, "Location": args.location,
        "Remote?": args.remote, "Comp Range": args.comp,
        "Applied Date": applied, "Resume Version": resume,
        "Cover Letter": args.cover, "Referral": args.referral,
        "Status": status, "Stage History": status, "Last Update": today,
        "Next Action": args.next_action, "Recruiter / Contact": args.contact,
        "Notes": args.note,
    }

    folder.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    if not new_file:  # repair a missing trailing newline before appending
        raw = path.read_bytes()
        if raw and not raw.endswith(b"\n"):
            with open(path, "a", encoding="utf-8") as f:
                f.write("\n")
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header, lineterminator="\n")
        if new_file:
            w.writeheader()
            print(f"Created {path}")
        w.writerow({h: row.get(h, "") for h in header})
    print(f"Logged: {args.company} — {args.position} ({status}"
          + (f", {applied}" if applied else "") + ")")


def cmd_apps_stats(args, cfg) -> None:
    vault = resolve_vault(args, cfg)
    _, rows = read_applications(apps_folder(vault, cfg))
    if not rows:
        sys.exit("No applications logged yet.")
    today = dt.date.today()
    week_ago = today - dt.timedelta(days=6)

    def applied_on(r):
        v = (r.get("Applied Date") or "").strip()
        # tolerate spreadsheet-app rewrites: 7/16/26 or 7/16/2026
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", v)
        if m:
            y = int(m[3]) + (2000 if int(m[3]) < 100 else 0)
            v = f"{y:04d}-{int(m[1]):02d}-{int(m[2]):02d}"
        try:
            return dt.date.fromisoformat(v)
        except ValueError:
            return None

    today_n = sum(1 for r in rows if applied_on(r) == today)
    week_n = sum(1 for r in rows if (d := applied_on(r)) and week_ago <= d <= today)
    interviewed = sum(1 for r in rows
                      if re.search(r"Phone Screen|Onsite|Team Match|Offer",
                                   r.get("Stage History") or "", re.I))
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r.get("Status") or "—"] = by_status.get(r.get("Status") or "—", 0) + 1

    print(f"\U0001f4e8 Today: {today_n} · last 7 days: {week_n} · total: {len(rows)}")
    print(f"Interviewed (≥1 round): {interviewed} "
          f"({100 * interviewed / len(rows):.1f}%)")
    for s, n in sorted(by_status.items(), key=lambda kv: -kv[1]):
        print(f"  {s}: {n}")


# --- LeetCode sync (PRE-24) -----------------------------------------------
# Uses LeetCode's public GraphQL endpoint (unofficial): recent accepted
# submissions for a public profile. Objective facts only (number, title,
# difficulty); the topic is left empty on purpose — it records how YOU solved
# the problem, and a sync cannot know that.

LEETCODE_GRAPHQL = "https://leetcode.com/graphql"


def _lc_graphql(query: str, variables: dict) -> dict:
    import json
    import urllib.request
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        LEETCODE_GRAPHQL, data=body,
        headers={"Content-Type": "application/json",
                 "Referer": "https://leetcode.com",
                 "User-Agent": "Mozilla/5.0 (prepdojo)"})
    with urllib.request.urlopen(req, timeout=15) as r:
        import json as _j
        payload = _j.load(r)
    if "data" not in payload or payload["data"] is None:
        raise RuntimeError(f"unexpected response: {str(payload)[:200]}")
    return payload["data"]


def fetch_recent_ac(username: str, limit: int) -> list[dict]:
    data = _lc_graphql(
        """query recentAc($username: String!, $limit: Int!) {
             recentAcSubmissionList(username: $username, limit: $limit) {
               title titleSlug timestamp } }""",
        {"username": username, "limit": limit})
    subs = data.get("recentAcSubmissionList")
    if subs is None:
        raise RuntimeError("no submission list — is the profile private or the username wrong?")
    return subs


def fetch_question(slug: str) -> dict:
    data = _lc_graphql(
        """query q($slug: String!) {
             question(titleSlug: $slug) {
               questionFrontendId title difficulty } }""",
        {"slug": slug})
    q = data.get("question")
    if not q:
        raise RuntimeError(f"question not found: {slug}")
    return {"num": q["questionFrontendId"], "title": q["title"],
            "difficulty": q["difficulty"]}


def cmd_sync_lc(args, cfg) -> None:
    vault = resolve_vault(args, cfg)
    username = args.username or cfg.get("leetcode", {}).get("username", "")
    if not username:
        sys.exit("No LeetCode username. Add under [leetcode] in config.toml:\n"
                 '    username = "your-leetcode-username"\n'
                 "or pass --username.")
    try:
        recent = fetch_recent_ac(username, args.limit)
    except Exception as e:
        sys.exit(f"Could not fetch from LeetCode ({e}). Nothing was written.")
    if not recent:
        print("No recent accepted submissions found.")
        return

    # Sync window: don't resurrect ancient history as sparse daily notes.
    # Priority: --since flag > [leetcode].sync_since in config > last 7 days.
    since_spec = args.since or cfg.get("leetcode", {}).get("sync_since", "")
    if since_spec == "all":
        since = dt.date.min
    elif since_spec:
        try:
            since = dt.date.fromisoformat(since_spec)
        except ValueError:
            sys.exit(f"Bad since date '{since_spec}' — use YYYY-MM-DD or 'all'.")
    else:
        since = dt.date.today() - dt.timedelta(days=7)

    tag = cfg["categories"]["lc"]["tag"]
    qcache: dict[str, dict] = {}
    added, dups, skipped, too_old = 0, 0, 0, 0
    for sub in recent:
        date = dt.date.fromtimestamp(int(sub["timestamp"]))
        if date < since:
            too_old += 1
            continue
        slug = sub["titleSlug"]
        if slug not in qcache:
            try:
                qcache[slug] = fetch_question(slug)
            except Exception as e:
                print(f"  skipped {slug}: {e}")
                skipped += 1
                continue
        q = qcache[slug]
        # topic intentionally absent — fill it in later with how you solved it
        entry = f"- LC #{q['num']} {q['title']} · {q['difficulty']} #{tag}"
        if args.dry_run:
            print(f"  would log {date.isoformat()}: {entry}")
            continue
        result = insert_entry(daily_note_path(vault, cfg, date), cfg, entry, vault, date)
        if result == "duplicate":
            dups += 1
        else:
            added += 1
            print(f"  logged {date.isoformat()}: LC #{q['num']} {q['title']} · {q['difficulty']}")
    if args.dry_run:
        print("Dry run — nothing written.")
    else:
        print(f"Sync done: {added} new, {dups} already logged"
              + (f", {skipped} skipped" if skipped else "")
              + (f", {too_old} older than {since.isoformat()} (ignored)" if too_old else "") + ".")
        if too_old:
            print("To include older solves: rerun with --since YYYY-MM-DD (or --since all),"
                  " or set sync_since in config.toml.")
        if added:
            print("New entries have no topic yet — fill in how you solved them "
                  "(dashboard shows them under 'Needs topic').")


def main() -> None:
    parser = argparse.ArgumentParser(prog="prepdojo", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vault", help="path to your Obsidian vault")
    sub = parser.add_subparsers(dest="command", required=True)

    p_log = sub.add_parser("log", help="log an entry into a daily note")
    p_log.add_argument("category", help="lc, mlfund, mlcode, mlsys, or bq")
    p_log.add_argument("text", help="what you did (for lc: problem, e.g. '#200 Number of Islands')")
    p_log.add_argument("-d", "--difficulty", default="", help="lc only: Easy/Medium/Hard or E/M/H")
    p_log.add_argument("-t", "--topic", default="", help="lc only: topic from the taxonomy")
    p_log.add_argument("--note", default="", help="short note, shows in the dashboard Notes column")
    p_log.add_argument("--conf", choices=list(CONFIDENCE), default="green",
                       help="mlfund only: confidence (default green)")
    p_log.add_argument("--date", default="today", help="today, yesterday, a weekday, or YYYY-MM-DD")
    p_log.set_defaults(func=cmd_log)

    p_streak = sub.add_parser("streak", help="print streak and per-category counts")
    p_streak.set_defaults(func=cmd_streak)

    p_topics = sub.add_parser("topics", help="list the LeetCode topic taxonomy")
    p_topics.set_defaults(func=cmd_topics)

    p_sync = sub.add_parser("sync-lc", help="pull accepted LeetCode submissions into daily notes")
    p_sync.add_argument("--username", default="", help="LeetCode username (or set [leetcode].username in config)")
    p_sync.add_argument("--limit", type=int, default=20, help="how many recent submissions to check (max ~20)")
    p_sync.add_argument("--since", default="", help="only sync solves on/after this date (YYYY-MM-DD, or 'all'); default: last 7 days")
    p_sync.add_argument("--dry-run", action="store_true", help="show what would be logged without writing")
    p_sync.set_defaults(func=cmd_sync_lc)

    p_apps = sub.add_parser("apps", help="job application tracking (CSV)")
    apps_sub = p_apps.add_subparsers(dest="apps_command", required=True)

    a_log = apps_sub.add_parser("log", help="log a job application")
    a_log.add_argument("company")
    a_log.add_argument("position")
    a_log.add_argument("-r", "--resume", default="", help="resume version id (validated against resume-versions.csv)")
    a_log.add_argument("--status", default="Applied", help="default Applied; use Wishlist if not yet submitted")
    a_log.add_argument("--date", default="today", help="applied date: today, yesterday, a weekday, or YYYY-MM-DD")
    a_log.add_argument("--req-id", default="", dest="req_id")
    a_log.add_argument("--link", default="", help="job posting URL")
    a_log.add_argument("--location", default="")
    a_log.add_argument("--remote", default="", help="Remote / Hybrid / Onsite")
    a_log.add_argument("--comp", default="", help="compensation range if posted")
    a_log.add_argument("--cover", default="", help="cover letter version")
    a_log.add_argument("--referral", default="")
    a_log.add_argument("--next-action", default="", dest="next_action")
    a_log.add_argument("--contact", default="", help="recruiter / contact")
    a_log.add_argument("--note", default="")
    a_log.set_defaults(func=cmd_apps_log)

    a_stats = apps_sub.add_parser("stats", help="application counts and pipeline")
    a_stats.set_defaults(func=cmd_apps_stats)

    args = parser.parse_args()
    args.func(args, load_config())


if __name__ == "__main__":
    main()
