#!/usr/bin/env python3
"""End-to-end generation smoke test. No Obsidian required.

Copies the repo to a temp dir (so a developer's personal config.toml is never
touched), generates into a scratch vault, and asserts the install contract:
placeholders all replaced, expected files present, reruns idempotent, user
edits preserved as .new, data files never overwritten, setup.py works
non-interactively. Exits nonzero on the first failure.

Run locally:  python3 ci/smoke_test.py
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

EXPECTED_VAULT_FILES = [
    "Interview Prep Dashboard.md",
    "Templates/Daily Note.md",
    "scripts/prepdojo-log-application.js",
    "scripts/prepdojo-update-application.js",
    "scripts/prepdojo-add-resume-version.js",
    "scripts/prepdojo-log-mlsys.js",
    "scripts/prepdojo-log-mock.js",
    ".obsidian/daily-notes.json",
    ".obsidian/plugins/quickadd/data.json",
    "Applications/applications.csv",
    "Applications/resume-versions.csv",
]

fail_count = 0


def check(cond, label):
    global fail_count
    print(("  ok  " if cond else "  FAIL") + "  " + label)
    if not cond:
        fail_count += 1


def run(args, cwd, stdin=subprocess.DEVNULL):
    return subprocess.run(
        [sys.executable] + args, cwd=str(cwd), stdin=stdin,
        capture_output=True, text=True)


def fresh_copy(tmp, name):
    dst = Path(tmp) / name
    shutil.copytree(
        REPO, dst,
        ignore=shutil.ignore_patterns(".git", "dist", "config.toml", "__pycache__"))
    return dst


def main():
    tmp = tempfile.mkdtemp(prefix="prepdojo-smoke-")
    repo = fresh_copy(tmp, "repo")
    vault = Path(tmp) / "vault"
    (vault / ".obsidian").mkdir(parents=True)

    print("generate.py: first install")
    r = run(["generate.py", str(vault)], repo)
    check(r.returncode == 0, "exits 0 (stderr: %s)" % r.stderr.strip()[:200])
    for rel in EXPECTED_VAULT_FILES:
        check((vault / rel).exists(), "installed " + rel)
    leftovers = [p for p in vault.rglob("*")
                 if p.is_file() and p.suffix in (".md", ".js", ".json")
                 and "@@" in p.read_text(encoding="utf-8", errors="ignore")]
    check(not leftovers, "no unreplaced @@placeholders@@ (%s)" % leftovers)
    check('path = "%s"' % vault in (repo / "config.toml").read_text(encoding="utf-8"),
          "positional vault path recorded in config.toml")

    print("generate.py: rerun is idempotent")
    r = run(["generate.py"], repo)  # no arg: uses recorded path
    check(r.returncode == 0, "exits 0")
    check("up to date" in r.stdout, "reports up to date")
    check(not list(vault.rglob("*.new.*")), "no .new files on a clean rerun")

    print("data files are never overwritten")
    csv = vault / "Applications/applications.csv"
    body = csv.read_text(encoding="utf-8")
    marker = "SmokeCo,Test Engineer" + ",," * 8
    csv.write_text(body + marker + "\n", encoding="utf-8")
    run(["generate.py"], repo)
    check(marker in csv.read_text(encoding="utf-8"), "appended CSV row survives rerun")

    print("user edits are preserved")
    dash = vault / "Interview Prep Dashboard.md"
    dash.write_text(dash.read_text(encoding="utf-8") + "\nMY EDIT\n", encoding="utf-8")
    r = run(["generate.py"], repo)
    check("PRESERVED" in r.stdout, "edited dashboard reported PRESERVED")
    check("MY EDIT" in dash.read_text(encoding="utf-8"), "edit still in place")
    check(list(vault.rglob("*.new.md")), ".new copy written beside it")
    r = run(["generate.py", "--force"], repo)
    check(r.returncode == 0 and "MY EDIT" not in dash.read_text(encoding="utf-8"),
          "--force takes the generated version")

    print("setup.py: non-interactive first run")
    repo2 = fresh_copy(tmp, "repo2")
    vault2 = Path(tmp) / "vault2"
    (vault2 / ".obsidian").mkdir(parents=True)
    r = run(["setup.py", str(vault2)], repo2)
    check(r.returncode == 0, "exits 0 (stderr: %s)" % r.stderr.strip()[:200])
    check((vault2 / "Interview Prep Dashboard.md").exists(), "dashboard installed")
    check('path = "%s"' % vault2 in (repo2 / "config.toml").read_text(encoding="utf-8"),
          "vault path recorded")

    print("setup.py: refuses to treat the repo as a vault")
    repo3 = fresh_copy(tmp, "repo3")
    r = run(["setup.py"], repo3)  # no path anywhere, cwd is the repo itself
    check(r.returncode != 0 and "can't be a vault" in r.stdout,
          "no-arg run inside the repo refuses")

    shutil.rmtree(tmp, ignore_errors=True)
    if fail_count:
        print("\n%d check(s) FAILED" % fail_count)
        sys.exit(1)
    print("\nall smoke checks passed")


if __name__ == "__main__":
    main()
