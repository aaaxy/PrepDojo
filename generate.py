#!/usr/bin/env python3
"""Generate personalized tracker files from config.toml and install them.

First-time setup? Use setup.py instead — it wraps this script and also
creates your config and installs the Obsidian plugins. generate.py is the
day-to-day tool for redeploying after config or template changes.

Usage:
    python3 generate.py                # build dist/ and install into the vault
    python3 generate.py --no-install   # build dist/ only
    python3 generate.py --force        # install, overwriting even edited files

The install target is resolved in this order:
    1. positional argument:  python3 generate.py /path/to/YourVault
    2. --install /path/to/vault
    3. PREPDOJO_VAULT environment variable
    4. `path` under [vault] in config.toml
If none is set, only dist/ is built (with a hint on how to enable install).

Requires Python 3.11+ (uses the standard-library TOML parser). No third-party
dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import uuid
import zipfile
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # Python < 3.11 fallback
    except ModuleNotFoundError:
        sys.exit(
            "On Python older than 3.11 the TOML parser isn't built in. Install it:\n"
            "    pip install tomli"
        )

ROOT = Path(__file__).parent
TEMPLATES = ROOT / "templates"
DIST = ROOT / "dist"

CATEGORY_KEYS = ["lc", "mlfund", "mlcode", "mlsys", "bq", "mock"]

# Every setting has a default; config.toml only needs what the user wants to
# change (at minimum: [vault] path). Full reference: docs/configuration.md
DEFAULT_CONFIG = {
    "vault": {
        "daily_notes_folder": "Calendar/Daily Notes",
        "date_format": "YYYY-MM-DD",
        "daily_note_template": "Templates/Daily Note.md",
        "dashboard_path": "Interview Prep Dashboard.md",
        "prep_heading": "## Interview Prep",
    },
    "categories": {
        "lc": {"name": "LeetCode", "tag": "lc",
               "hotkey": {"modifiers": ["Mod", "Shift"], "key": "L"}},
        "mlfund": {"name": "ML Fundamentals", "tag": "mlfund",
                   "hotkey": {"modifiers": ["Mod", "Shift"], "key": "M"}},
        "mlcode": {"name": "ML Coding", "tag": "mlcode"},
        "mlsys": {"name": "ML System Design", "tag": "mlsys"},
        "bq": {"name": "Behavioral", "tag": "bq"},
        "mock": {"name": "Mock Interviews", "tag": "mock"},
    },
    "leetcode": {
        "difficulties": ["Easy", "Medium", "Hard"],
        "topics": [
            "arrays & hashing", "two pointers", "sliding window", "stack",
            "binary search", "linked list", "trees", "heap", "backtracking",
            "graphs", "bfs/dfs", "dp", "greedy", "intervals", "bit manipulation",
        ],
    },
    "applications": {
        "folder": "Applications",
        "hotkey": {"modifiers": ["Mod", "Shift"], "key": "A"},
    },
}


def deep_merge(base: dict, override: dict) -> dict:
    """Recursive dict merge; values in `override` win."""
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out

# Source types for the guided ML system design flow; override with
# `sources = [...]` under [categories.mlsys] in config.toml.
MLSYS_DEFAULT_SOURCES = ["question", "blog", "video", "course", "paper", "project", "other"]

# Session types for mock-interview logging; override with `types = [...]`
# under [categories.mock] in config.toml.
MOCK_DEFAULT_TYPES = ["coding", "behavioral", "system design"]

# Starter headers for the job-application CSVs (kept in sync with prepdojo.py
# and the dashboard's Job Applications section).
APPLICATIONS_HEADER = ("Company,Position Title,Req ID,Job Link,Location,Remote?,"
                       "Comp Range,Applied Date,Resume Version,Cover Letter,Referral,"
                       "Status,Stage History,Last Update,Next Action,"
                       "Recruiter / Contact,Notes,Follow-up Date\n")
RESUME_VERSIONS_HEADER = ("Version ID,Short Description,Emphasis / Angle,"
                          "Target Role Type,File Path,Date Last Updated,Notes\n")

# One QuickAdd capture per category: (display name suffix, prompt format)
CAPTURE_FORMATS = {
    "lc": "- LC {{VALUE:Problem name (e.g. #200 Number of Islands)}} · {{VALUE:@DIFFS@}} · {{VALUE:@TOPICS@}} #@TAG@\n",
    "mlfund": "- {{VALUE:Topic reviewed}} · {{VALUE:\U0001f7e2,\U0001f7e1,\U0001f534}} #@TAG@\n",
    "mlcode": "- {{VALUE:What did you implement?}} #@TAG@\n",
    "bq": "- {{VALUE:Story or question practiced}} #@TAG@\n",
}


def stable_id(key: str) -> str:
    """Deterministic UUID per category so hotkeys.json always matches data.json."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"prepdojo/{key}"))


def load_config() -> dict:
    cfg_path = ROOT / "config.toml"
    template = ROOT / "config-template.toml"
    if not cfg_path.exists():
        if not template.exists():
            sys.exit("No config found. Expected config.toml or config-template.toml "
                     "next to generate.py.")
        # First run: bootstrap a personal, gitignored config from the template.
        shutil.copyfile(template, cfg_path)
        print("Created config.toml from config-template.toml — edit it to customize, "
              "then rerun.")
    with open(cfg_path, "rb") as f:
        return deep_merge(DEFAULT_CONFIG, tomllib.load(f))


def replacements(cfg: dict) -> dict:
    v, lc = cfg["vault"], cfg["leetcode"]
    rep = {
        "@@DAILY_NOTES_FOLDER@@": v["daily_notes_folder"],
        "@@DATE_FORMAT@@": v["date_format"],
        "@@DAILY_NOTE_TEMPLATE@@": v["daily_note_template"],
        "@@DASHBOARD_PATH@@": v["dashboard_path"],
        "@@PREP_HEADING@@": v["prep_heading"],
        "@@TOPICS_CSV@@": ",".join(lc["topics"]),
        "@@DIFFICULTIES_CSV@@": ",".join(lc["difficulties"]),
        "@@DIFFICULTIES_PIPE@@": "|".join(lc["difficulties"]),
        "@@TOPICS_INLINE@@": ", ".join(f"`{t}`" for t in lc["topics"]),
        "@@APPLICATIONS_FOLDER@@": cfg.get("applications", {}).get(
            "folder", "Career/Job Hunting/NG/Applications"),
        "@@LC_USERNAME@@": cfg.get("leetcode", {}).get("username", ""),
        "@@MLSYS_SOURCES_JSON@@": json.dumps(
            cfg["categories"]["mlsys"].get("sources", MLSYS_DEFAULT_SOURCES)),
        "@@MOCK_TYPES_JSON@@": json.dumps(
            cfg["categories"]["mock"].get("types", MOCK_DEFAULT_TYPES)),
    }
    for key in CATEGORY_KEYS:
        cat = cfg["categories"][key]
        rep[f"@@TAG_{key.upper()}@@"] = cat["tag"]
        rep[f"@@NAME_{key.upper()}@@"] = cat["name"]
    return rep


def record_vault_path(vault: str) -> None:
    """Persist a positionally-given vault path into config.toml, so later
    runs can be plain `python3 generate.py`. --install stays a one-off
    override and is never recorded."""
    cfg_path = ROOT / "config.toml"
    if not cfg_path.exists():
        return
    text = cfg_path.read_text(encoding="utf-8")
    line = f'path = "{vault}"'
    placeholder = '# path = "/absolute/path/to/YourVault"'
    if re.search(r'^path = ".*"$', text, flags=re.M):
        new_text = re.sub(r'^path = ".*"$', line.replace("\\", "\\\\"), text,
                          count=1, flags=re.M)
    elif placeholder in text:
        new_text = text.replace(placeholder, line, 1)
    else:
        new_text = text.replace("[vault]", f"[vault]\n{line}", 1)
    if new_text != text:
        cfg_path.write_text(new_text, encoding="utf-8")
        print(f"  recorded vault path in config.toml: {vault}")


def render(text: str, rep: dict) -> str:
    for k, val in rep.items():
        text = text.replace(k, val)
    leftovers = [line for line in text.splitlines() if "@@" in line]
    if leftovers:
        sys.exit(f"Unreplaced placeholder remains: {leftovers[0].strip()}")
    return text


def build_quickadd(cfg: dict) -> dict:
    v, lc = cfg["vault"], cfg["leetcode"]
    capture_to = (
        f"{v['daily_notes_folder']}/"
        f"{{{{VDATE:Which day?,{v['date_format']}|today}}}}.md"
    )
    choices = []
    for key in CATEGORY_KEYS:
        cat = cfg["categories"][key]
        if key == "mock":
            # Guided macro flow (type + reflections) — see log-mock.js
            choices.append({
                "id": stable_id(key),
                "name": f"Log {cat['name']}",
                "type": "Macro",
                "command": True,
                "runOnStartup": False,
                "macro": {
                    "id": stable_id("mock-macro"),
                    "name": f"Log {cat['name']}",
                    "commands": [{
                        "name": "prepdojo-log-mock",
                        "type": "UserScript",
                        "path": "scripts/prepdojo-log-mock.js",
                        "settings": {},
                    }],
                },
            })
            continue
        if key == "mlsys":
            # Guided macro flow (topic/source/link/notes) — see log-mlsys.js
            choices.append({
                "id": stable_id(key),
                "name": f"Log {cat['name']}",
                "type": "Macro",
                "command": True,
                "runOnStartup": False,
                "macro": {
                    "id": stable_id("mlsys-macro"),
                    "name": f"Log {cat['name']}",
                    "commands": [{
                        "name": "prepdojo-log-mlsys",
                        "type": "UserScript",
                        "path": "scripts/prepdojo-log-mlsys.js",
                        "settings": {},
                    }],
                },
            })
            continue
        fmt = (
            CAPTURE_FORMATS[key]
            .replace("@DIFFS@", ",".join(lc["difficulties"]))
            .replace("@TOPICS@", ",".join(lc["topics"]))
            .replace("@TAG@", cat["tag"])
        )
        choices.append({
            "id": stable_id(key),
            "name": f"Log {cat['name']}",
            "type": "Capture",
            "command": True,
            "appendLink": False,
            "captureTo": capture_to,
            "captureToActiveFile": False,
            "captureToCanvasNodeId": "",
            "activeFileWritePosition": "cursor",
            "createFileIfItDoesntExist": {
                "enabled": True,
                "createWithTemplate": True,
                "template": v["daily_note_template"],
            },
            "format": {"enabled": True, "format": fmt},
            "insertAfter": {
                "enabled": True,
                "after": v["prep_heading"],
                "insertAtEnd": False,
                "considerSubsections": False,
                "createIfNotFound": True,
                "createIfNotFoundLocation": "top",
                "inline": False,
                "replaceExisting": False,
                "blankLineAfterMatchMode": "auto",
            },
            "newLineCapture": {"enabled": False, "direction": "below"},
            "prepend": False,
            "task": False,
            "openFile": False,
            "fileOpening": {
                "location": "tab", "direction": "vertical",
                "mode": "default", "focus": True,
            },
            "templater": {"afterCapture": "none"},
        })
    # In-Obsidian application logging: a macro choice running the generated
    # user script (prompts for company/position/version/status, appends a
    # properly quoted CSV row).
    choices.append({
        "id": stable_id("apps-update"),
        "name": "Update Application",
        "type": "Macro",
        "command": True,
        "runOnStartup": False,
        "macro": {
            "id": stable_id("apps-update-macro"),
            "name": "Update Application",
            "commands": [{
                "name": "prepdojo-update-application",
                "type": "UserScript",
                "path": "scripts/prepdojo-update-application.js",
                "settings": {},
            }],
        },
    })
    choices.append({
        "id": stable_id("apps-log"),
        "name": "Log Application",
        "type": "Macro",
        "command": True,
        "runOnStartup": False,
        "macro": {
            "id": stable_id("apps-log-macro"),
            "name": "Log Application",
            "commands": [{
                "name": "prepdojo-log-application",
                "type": "UserScript",
                "path": "scripts/prepdojo-log-application.js",
                "settings": {},
            }],
        },
    })
    choices.append({
        "id": stable_id("resume-version-add"),
        "name": "Add Resume Version",
        "type": "Macro",
        "command": True,
        "runOnStartup": False,
        "macro": {
            "id": stable_id("resume-version-add-macro"),
            "name": "Add Resume Version",
            "commands": [{
                "name": "prepdojo-add-resume-version",
                "type": "UserScript",
                "path": "scripts/prepdojo-add-resume-version.js",
                "settings": {},
            }],
        },
    })
    return {
        "choices": choices,
        "inputPrompt": "single-line",
        "persistInputPromptDrafts": True,
        "useSelectionAsCaptureValue": True,
        "devMode": False,
        "templateFolderPath": "",
        "announceUpdates": "major",
        "globalVariables": {},
        "onePageInputEnabled": False,
        "disableOnlineFeatures": True,
        "enableRibbonIcon": False,
        "showCaptureNotification": True,
        "showInputCancellationNotification": False,
        "enableTemplatePropertyTypes": False,
        "dateAliases": {
            "t": "today", "tm": "tomorrow", "yd": "yesterday",
            "nw": "next week", "nm": "next month", "ny": "next year",
            "lw": "last week", "lm": "last month", "ly": "last year",
        },
    }


def build_prepdojo_json(cfg: dict) -> str:
    """Machine-readable install contract for the AI plugin skills (PRE-31).

    Installed at the vault root as prepdojo.json and tracked in the byte
    manifest. The PrepDojo plugin skills read this file at session start to
    learn the user's paths, tags, topics, and CSV schema; generate.py is the
    only writer. Output is deterministic so reruns stay byte-identical.
    """
    v, lc = cfg["vault"], cfg["leetcode"]
    cats = {}
    for key in CATEGORY_KEYS:
        cat = cfg["categories"][key]
        entry = {"name": cat["name"], "tag": cat["tag"]}
        if key == "mlsys":
            entry["sources"] = cat.get("sources", MLSYS_DEFAULT_SOURCES)
        if key == "mock":
            entry["types"] = cat.get("types", MOCK_DEFAULT_TYPES)
        cats[key] = entry
    doc = {
        "prepdojo": {"schema": 1},
        "vault": {
            "daily_notes_folder": v["daily_notes_folder"],
            "date_format": v["date_format"],
            "daily_note_template": v["daily_note_template"],
            "dashboard_path": v["dashboard_path"],
            "prep_heading": v["prep_heading"],
        },
        "entry_format": {"separator": " · "},
        "categories": cats,
        "leetcode": {
            "difficulties": lc["difficulties"],
            "topics": lc["topics"],
            # Presence only, never the username itself: the skills only need
            # to know whether the import button/CLI is available to point to.
            "import_configured": bool(lc.get("username")),
        },
        "applications": {
            "folder": cfg["applications"]["folder"],
            "applications_csv": "applications.csv",
            "resume_versions_csv": "resume-versions.csv",
            "applications_columns": APPLICATIONS_HEADER.rstrip("\n").split(","),
            "resume_versions_columns": RESUME_VERSIONS_HEADER.rstrip("\n").split(","),
        },
    }
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def build_hotkeys(cfg: dict) -> dict:
    out = {}
    for key in CATEGORY_KEYS:
        hotkey = cfg["categories"][key].get("hotkey")
        if hotkey:
            out[f"quickadd:choice:{stable_id(key)}"] = [
                {"modifiers": hotkey["modifiers"], "key": hotkey["key"]}
            ]
    apps_hotkey = cfg.get("applications", {}).get("hotkey")
    if apps_hotkey:
        out[f"quickadd:choice:{stable_id('apps-log')}"] = [
            {"modifiers": apps_hotkey["modifiers"], "key": apps_hotkey["key"]}
        ]
    return out


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vault", nargs="?", metavar="VAULT",
                        help="vault to install into (same as setup.py; optional if "
                             "config.toml already records the path)")
    parser.add_argument("--install", metavar="VAULT",
                        help="vault to install into (overrides PREPDOJO_VAULT and config)")
    parser.add_argument("--no-install", action="store_true",
                        help="build dist/ only, skip installing")
    parser.add_argument("--force", action="store_true", help="overwrite existing files when installing")
    args = parser.parse_args()

    cfg = load_config()
    rep = replacements(cfg)
    v = cfg["vault"]

    if DIST.exists():
        # Best-effort clean; every file below is (re)written anyway, this only
        # clears leftovers from previous configs (e.g. renamed paths).
        shutil.rmtree(DIST, ignore_errors=True)

    print("Generating into dist/ ...")

    # Vault-side markdown
    daily_note = render((TEMPLATES / "vault" / "daily-note.md").read_text(encoding="utf-8"), rep)
    dashboard = render((TEMPLATES / "vault" / "dashboard.md").read_text(encoding="utf-8"), rep)
    write(DIST / "vault" / v["daily_note_template"], daily_note)
    write(DIST / "vault" / v["dashboard_path"], dashboard)

    # Starter job-application CSVs (headers only; real data never lives in dist)
    apps_folder = rep["@@APPLICATIONS_FOLDER@@"]
    write(DIST / "vault" / apps_folder / "applications.csv", APPLICATIONS_HEADER)
    write(DIST / "vault" / apps_folder / "resume-versions.csv", RESUME_VERSIONS_HEADER)

    # QuickAdd user scripts for in-Obsidian logging
    app_script = render((TEMPLATES / "vault" / "log-application.js").read_text(encoding="utf-8"), rep)
    write(DIST / "vault" / "scripts" / "prepdojo-log-application.js", app_script)
    ver_script = render((TEMPLATES / "vault" / "add-resume-version.js").read_text(encoding="utf-8"), rep)
    write(DIST / "vault" / "scripts" / "prepdojo-add-resume-version.js", ver_script)
    mlsys_script = render((TEMPLATES / "vault" / "log-mlsys.js").read_text(encoding="utf-8"), rep)
    write(DIST / "vault" / "scripts" / "prepdojo-log-mlsys.js", mlsys_script)
    upd_script = render((TEMPLATES / "vault" / "update-application.js").read_text(encoding="utf-8"), rep)
    write(DIST / "vault" / "scripts" / "prepdojo-update-application.js", upd_script)
    mock_script = render((TEMPLATES / "vault" / "log-mock.js").read_text(encoding="utf-8"), rep)
    write(DIST / "vault" / "scripts" / "prepdojo-log-mock.js", mock_script)

    # Obsidian config
    write(DIST / "obsidian" / "daily-notes.json", json.dumps({
        "folder": v["daily_notes_folder"],
        "format": v["date_format"],
        "template": v["daily_note_template"].removesuffix(".md"),
    }, indent=2) + "\n")
    write(DIST / "obsidian" / "plugins" / "quickadd" / "data.json",
          json.dumps(build_quickadd(cfg), indent=2, ensure_ascii=False) + "\n")
    write(DIST / "obsidian" / "hotkeys-snippet.json",
          json.dumps(build_hotkeys(cfg), indent=2) + "\n")

    # Machine-readable contract for the AI plugin skills (PRE-31)
    write(DIST / "vault" / "prepdojo.json", build_prepdojo_json(cfg))

    # Claude skill (deprecated: superseded by the PrepDojo plugin — see README.
    # Kept for one more release so existing installs keep working.)
    skill = render((TEMPLATES / "skill" / "SKILL.md").read_text(encoding="utf-8"), rep)
    write(DIST / "claude-skill" / "lc-logger" / "SKILL.md", skill)
    skill_pkg = DIST / "claude-skill" / "lc-logger.skill"
    with zipfile.ZipFile(skill_pkg, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("lc-logger/SKILL.md", skill)
    print(f"  wrote {skill_pkg.relative_to(ROOT)}")
    print("  note: dist/claude-skill is deprecated — install the PrepDojo "
          "plugin instead (README, AI logging)")

    # Install by default; the target comes from the flag, the env var, or config.
    target = None if args.no_install else (
        args.vault or args.install or os.environ.get("PREPDOJO_VAULT") or cfg["vault"].get("path"))
    if target is None and not args.no_install:
        print(
            "\nBuilt dist/ only — no vault to install into. To install automatically,\n"
            "set `path` under [vault] in config.toml (or pass --install /path/to/vault).\n"
            "To install by hand instead, see the copy table in README.md."
        )
    if target:
        vault = Path(target).expanduser()
        if not vault.is_dir():
            sys.exit(f"Vault directory not found: {vault}\n"
                     "(check `path` under [vault] in config.toml, or pass --install)")
        if args.vault:
            record_vault_path(str(vault))
        print(f"\nInstalling into {vault} ...")

        # Manifest of checksums from previous installs. A target file is only
        # overwritten if it still matches the checksum we last installed,
        # i.e. the user never edited it. Edited files are preserved and the
        # fresh version is written alongside as *.new.* for manual merging.
        manifest_path = vault / ".obsidian" / "prepdojo-manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            manifest = {}

        def checksum(path: Path) -> str:
            return hashlib.sha256(path.read_bytes()).hexdigest()

        pairs = [
            (DIST / "vault" / v["daily_note_template"], vault / v["daily_note_template"]),
            (DIST / "vault" / v["dashboard_path"], vault / v["dashboard_path"]),
            (DIST / "vault" / "scripts" / "prepdojo-log-application.js",
             vault / "scripts" / "prepdojo-log-application.js"),
            (DIST / "vault" / "scripts" / "prepdojo-add-resume-version.js",
             vault / "scripts" / "prepdojo-add-resume-version.js"),
            (DIST / "vault" / "scripts" / "prepdojo-log-mlsys.js",
             vault / "scripts" / "prepdojo-log-mlsys.js"),
            (DIST / "vault" / "scripts" / "prepdojo-update-application.js",
             vault / "scripts" / "prepdojo-update-application.js"),
            (DIST / "vault" / "scripts" / "prepdojo-log-mock.js",
             vault / "scripts" / "prepdojo-log-mock.js"),
            (DIST / "obsidian" / "daily-notes.json", vault / ".obsidian" / "daily-notes.json"),
            (DIST / "vault" / "prepdojo.json", vault / "prepdojo.json"),
        ]
        def clean_stale_new(dst: Path) -> None:
            """A .new copy is only meaningful while its original is unresolved;
            once the original installs cleanly, the leftover is trash."""
            stale = dst.with_name(dst.stem + ".new" + dst.suffix)
            if stale.exists():
                try:
                    stale.unlink()
                    print(f"  removed stale: {stale}")
                except OSError:
                    pass

        for src, dst in pairs:
            key = dst.relative_to(vault).as_posix()
            src_sum = checksum(src)
            if dst.exists():
                dst_sum = checksum(dst)
                if dst_sum == src_sum:
                    print(f"  up to date: {dst}")
                    manifest[key] = src_sum
                    clean_stale_new(dst)
                    continue
                user_modified = manifest.get(key) is not None and manifest[key] != dst_sum
                unknown_origin = manifest.get(key) is None
                if (user_modified or unknown_origin) and not args.force:
                    new_path = dst.with_name(dst.stem + ".new" + dst.suffix)
                    shutil.copyfile(src, new_path)
                    reason = "edited by you" if user_modified else "not installed by prepdojo"
                    print(f"  PRESERVED ({reason}): {dst}")
                    print(f"    new version written to: {new_path}")
                    print(f"    merge manually, or rerun with --force to overwrite")
                    continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            manifest[key] = src_sum
            print(f"  installed {dst}")
            clean_stale_new(dst)

        # QuickAdd config: co-owned with the plugin (QuickAdd rewrites the
        # file on every launch, adding its own bookkeeping), so byte-level
        # tracking can't work. Merge semantically instead: PrepDojo owns
        # exactly the choices carrying its stable IDs; everything else —
        # plugin settings, the user's own choices — is left untouched.
        qa_src = DIST / "obsidian" / "plugins" / "quickadd" / "data.json"
        qa_dst = vault / ".obsidian" / "plugins" / "quickadd" / "data.json"
        generated_qa = json.loads(qa_src.read_text(encoding="utf-8"))
        if not qa_dst.exists():
            qa_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(qa_src, qa_dst)
            print(f"  installed {qa_dst}")
        else:
            try:
                current_qa = json.loads(qa_dst.read_text(encoding="utf-8"))
                ours = {c["id"]: c for c in generated_qa["choices"]}
                merged, seen = [], set()
                for c in current_qa.get("choices", []):
                    cid = c.get("id")
                    if cid in ours:
                        merged.append(ours[cid])
                        seen.add(cid)
                    else:
                        merged.append(c)  # user's own choice: keep verbatim
                merged += [c for cid, c in ours.items() if cid not in seen]
                if merged == current_qa.get("choices"):
                    print(f"  up to date: {qa_dst}")
                else:
                    current_qa["choices"] = merged
                    qa_dst.write_text(
                        json.dumps(current_qa, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
                    print(f"  updated PrepDojo choices in: {qa_dst}")
                clean_stale_new(qa_dst)
            except (json.JSONDecodeError, KeyError):
                new_path = qa_dst.with_name("data.new.json")
                shutil.copyfile(qa_src, new_path)
                print(f"  PRESERVED (could not parse): {qa_dst}")
                print(f"    generated version written to: {new_path}")
        # this file is merge-managed now; drop any stale byte-tracking entry
        manifest.pop(".obsidian/plugins/quickadd/data.json", None)

        # Data files: create only if absent, never overwrite, never .new —
        # these hold the user's records, not generated content.
        for name in ("applications.csv", "resume-versions.csv"):
            src = DIST / "vault" / apps_folder / name
            dst = vault / apps_folder / name
            if dst.exists():
                print(f"  kept (data file): {dst}")
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            print(f"  installed (empty starter): {dst}")

        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(
            "\nNot auto-installed: hotkeys. Merge dist/obsidian/hotkeys-snippet.json\n"
            "into <vault>/.obsidian/hotkeys.json yourself (or assign hotkeys in\n"
            "Settings → Hotkeys), so your existing hotkeys are never clobbered."
        )

    print("\nDone. See README.md for what to do with each file in dist/.")


if __name__ == "__main__":
    main()
