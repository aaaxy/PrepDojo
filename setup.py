#!/usr/bin/env python3
"""One-command first-time setup for PrepDojo.

Runs the scriptable parts of the Quick start, in order:
  1. create your personal config.toml from the template
  2. generate and install the vault files (dashboard, daily-note template,
     QuickAdd config)
  3. install + enable the required Obsidian plugins via the Obsidian CLI

A few steps can only be done in Obsidian's GUI (enabling the CLI, toggling
Dataview's JavaScript queries, assigning hotkeys). This script does everything
else and prints exactly what's left at the end.

Usage:
    python3 setup.py /path/to/YourVault
        Pass your vault's path; it is recorded in config.toml for you.
        (PREPDOJO_VAULT env var works too.)
    python3 setup.py
        No path: offers to install into the current folder, so running it
        from inside your vault needs no arguments at all.

Requires Python 3.9+. On 3.9/3.10 it installs the `tomli` package for you;
on 3.11+ nothing extra is needed. Runs on macOS, Linux, and Windows.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent
PLUGINS = ["dataview", "quickadd", "calendar"]


def step(n: int, total: int, msg: str) -> None:
    print(f"\n[{n}/{total}] {msg}")


def ensure_config() -> bool:
    """Create config.toml from the template if missing. Returns True if created."""
    cfg = ROOT / "config.toml"
    template = ROOT / "config-template.toml"
    if cfg.exists():
        print("  config.toml already exists — leaving your settings untouched")
        return False
    if not template.exists():
        sys.exit("  config-template.toml is missing; cannot create config.toml")
    cfg.write_bytes(template.read_bytes())
    print("  created config.toml from config-template.toml")
    return True


def config_vault_path() -> Optional[str]:
    """Read the vault path from config.toml, ignoring the template placeholder."""
    cfg = ROOT / "config.toml"
    if not cfg.exists():
        return None
    for line in cfg.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if (s.startswith("path ") or s.startswith("path=")) and "=" in s:
            val = s.split("=", 1)[1].strip().strip('"').strip("'")
            if val and "/absolute/path/to/YourVault" not in val:
                return val
    return None


def resolve_vault(just_created: bool) -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    env = os.environ.get("PREPDOJO_VAULT")
    if env:
        print(f"  using PREPDOJO_VAULT: {env}")
        return env
    from_config = config_vault_path()
    if from_config:
        print(f"  using vault path from config.toml: {from_config}")
        return from_config

    # No path given anywhere: offer the folder the command was run from.
    cwd = Path.cwd()
    if cwd.resolve() == ROOT.resolve():
        print("\nNo vault path given, and the current folder is the PrepDojo repo")
        print("itself, which can't be a vault. Rerun with your vault's path:")
        print("    python3 setup.py /path/to/YourVault")
        sys.exit(1)
    try:
        answer = input(f"\nNo vault path given. Install into the current folder?\n    {cwd}\n[y/N]: ")
    except EOFError:
        print("\nNo interactive terminal and no vault path. Rerun with:")
        print("    python3 setup.py /path/to/YourVault")
        sys.exit(1)
    if answer.strip().lower() in ("y", "yes"):
        return str(cwd)
    print("Stopped. Rerun with  python3 setup.py /path/to/YourVault")
    sys.exit(0)


def write_vault_path(vault: str) -> None:
    """Record the vault path in config.toml so every later command — bare
    generate.py deploys, prepdojo.py logging — works without flags. Respects a
    path the user already set; only fills the commented-out placeholder."""
    cfg = ROOT / "config.toml"
    text = cfg.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if (stripped.startswith("path ") or stripped.startswith("path=")) \
                and "/absolute/path/to/YourVault" not in stripped:
            print("  config.toml already sets a vault path — leaving it as is")
            return
    # replace an uncommented placeholder line, if present, so it can't linger
    text = text.replace('path = "/absolute/path/to/YourVault"\n', "", 1)
    resolved = Path(vault).expanduser().resolve()
    path_line = f'path = "{resolved}"'
    placeholder = '# path = "/absolute/path/to/YourVault"'
    if placeholder in text:
        text = text.replace(placeholder, path_line, 1)
    else:
        text = text.replace("[vault]", f"[vault]\n{path_line}", 1)
    cfg.write_text(text, encoding="utf-8")
    print(f"  recorded vault path in config.toml: {resolved}")


def ensure_tomli() -> None:
    """generate.py/prepdojo.py parse config.toml with tomllib, which is only
    built in on Python 3.11+. On older Pythons, install the drop-in `tomli`."""
    if sys.version_info >= (3, 11):
        return  # tomllib is in the standard library
    if importlib.util.find_spec("tomli") is not None:
        return  # already available
    print("  Python < 3.11 has no built-in TOML parser — installing 'tomli'...")
    result = subprocess.run([sys.executable, "-m", "pip", "install", "tomli"])
    if result.returncode != 0:
        sys.exit(
            "  Could not install tomli automatically. Install it and rerun:\n"
            f"    {sys.executable} -m pip install tomli"
        )
    print("  tomli installed")


def run_generate(vault: str) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "generate.py"), "--install", vault]
    )
    if result.returncode != 0:
        sys.exit("  generate.py failed — fix the error above, then rerun.")


MANUAL_PLUGINS = (
    "  Install the three plugins by hand any time:\n"
    "    1. Settings → Community plugins → turn off Restricted mode\n"
    "       (new vaults start with it on, and it blocks community plugins).\n"
    "    2. Browse → install and enable Dataview, QuickAdd, Calendar."
)


def run_cli(args: list, timeout: int) -> tuple:
    """Run an Obsidian CLI command without risking a hang. Output goes to a
    temp file, not a pipe: the CLI may launch the Obsidian app, which inherits
    a pipe and holds it open forever, so a piped run never returns. A timeout
    guards the wait as well. Returns (returncode or None, output)."""
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as out:
        try:
            proc = subprocess.run(args, stdout=out, stderr=subprocess.STDOUT,
                                  timeout=timeout)
        except (subprocess.TimeoutExpired, OSError):
            return None, ""
        out.seek(0)
        return proc.returncode, out.read()


def active_vault(obsidian: str) -> Optional[str]:
    """Path of the vault Obsidian currently has open, or None if undeterminable.
    The CLI installs plugins into THIS vault — it can't target an arbitrary
    folder — so we use it to make sure we install into the right one."""
    rc, out = run_cli([obsidian, "vault", "info=path"], timeout=8)
    if rc != 0:  # nonzero, or None on timeout
        return None
    # Output may carry Obsidian's own warning lines; the path is the last one.
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    return lines[-1] if lines else None


def launch_vault(vault: Path) -> None:
    """Open the target vault in Obsidian, detached. The CLI only answers
    queries while the app is running: invoked cold, it boots the whole app
    and never returns. So the app must be up, with the right vault, before
    any CLI call. The obsidian:// URI does both."""
    from urllib.parse import quote
    uri = "obsidian://open?path=" + quote(str(vault))
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", uri], timeout=15)
        elif os.name == "nt":
            os.startfile(uri)  # noqa — Windows only
        else:
            subprocess.run(["xdg-open", uri], timeout=15)
    except Exception:
        pass


def install_plugins(vault: str) -> None:
    obsidian = shutil.which("obsidian")
    if obsidian:
        print(f"  found the Obsidian CLI: {obsidian}", flush=True)
    if not obsidian:
        print(
            "  The 'obsidian' command isn't on your PATH, so plugins were NOT\n"
            "  installed automatically. That's expected if either:\n"
            "    - you're on Obsidian older than 1.12 (it has no CLI), or\n"
            "    - you haven't enabled the CLI yet: open Obsidian → Settings →\n"
            "      General → Command line interface → register it, then rerun this\n"
            "      script to finish the plugin install automatically.\n"
            + MANUAL_PLUGINS
        )
        return

    # The Obsidian CLI installs into whichever vault is currently open — it
    # cannot target a path or an unregistered folder. So refuse to install
    # unless the open vault is the one being set up, to avoid dropping plugins
    # into the wrong vault.
    target = Path(vault).expanduser().resolve()
    if sys.stdin.isatty():
        # Open the vault before any CLI query: queries only answer while the
        # app is running, and against a cold app each one burns its timeout.
        # If Obsidian is already up this just focuses the window.
        print("  opening your vault in Obsidian...", flush=True)
        launch_vault(target)
        print("  waiting for Obsidian to answer (up to a minute)...", flush=True)
        current = None
        for _ in range(8):
            current = active_vault(obsidian)
            if current is not None and Path(current).resolve() == target:
                break
            time.sleep(4)
    else:
        current = active_vault(obsidian)
    if current is None or Path(current).resolve() != target:
        print(
            "  Skipping automatic plugin install. The Obsidian CLI installs into\n"
            "  the vault currently open in Obsidian, which isn't your target vault:\n"
            f"    open now: {current or 'unknown (the CLI gave no answer)'}\n"
            f"    target:   {target}\n"
            "  Open your target vault in Obsidian, then rerun this script — or:\n"
            + MANUAL_PLUGINS
        )
        return

    # Community plugins can only be installed with Restricted Mode off.
    run_cli([obsidian, "plugins:restrict", "off"], timeout=30)
    failed = []
    for pid in PLUGINS:
        print(f"  installing {pid} (up to 2 minutes)...", flush=True)
        rc, _ = run_cli([obsidian, "plugin:install", f"id={pid}", "enable"], timeout=120)
        if rc != 0:
            failed.append(pid)
    installed = [p for p in PLUGINS if p not in failed]
    if installed:
        print("  installed and enabled: " + ", ".join(installed))
    if failed:
        print("  could not install: " + ", ".join(failed)
              + " — add them by hand from Settings → Community plugins → Browse")


def ask_preferences(created: bool) -> None:
    """First-run questions; answers are written into config.toml.
    Enter skips/accepts the default. Non-interactive runs skip quietly."""
    if not created:
        return  # existing config: don't re-ask, edit config.toml instead
    cfg = ROOT / "config.toml"
    try:
        print(
            "\nTwo quick questions (press Enter to skip or accept the default).\n"
            "\nPrepDojo can import your recent accepted LeetCode submissions\n"
            "automatically — the dashboard's Import button pulls them into your\n"
            "log with one click. That needs your LeetCode username (public\n"
            "profile data only; no password, nothing is posted)."
        )
        username = input("LeetCode username (Enter to skip): ").strip().strip('"')
        print(
            "\nIf you already keep daily notes in this vault, PrepDojo should\n"
            "log into the same folder. Otherwise the default works fine."
        )
        folder = input(
            'Daily notes folder (press Enter to use "Calendar/Daily Notes"): '
        ).strip().strip('"')
    except EOFError:
        print("\n(no interactive terminal — keeping defaults; edit config.toml to change)")
        return
    text = cfg.read_text(encoding="utf-8")
    if username:
        anchor = '# username = "your-leetcode-username"'
        if anchor in text:
            text = text.replace(anchor, f'username = "{username}"', 1)
    if folder and folder != "Calendar/Daily Notes":
        anchor = 'daily_notes_folder = "Calendar/Daily Notes"'
        if anchor in text:
            text = text.replace(anchor, f'daily_notes_folder = "{folder}"', 1)
    cfg.write_text(text, encoding="utf-8")
    if username or (folder and folder != "Calendar/Daily Notes"):
        print("  recorded in config.toml")


def main() -> None:
    if sys.version_info < (3, 9):
        sys.exit(
            f"PrepDojo needs Python 3.9+ (you have {sys.version.split()[0]}).\n"
            "Install a newer Python and run it explicitly, e.g. python3.11 setup.py ..."
        )

    print("PrepDojo setup")
    print("==============")
    print(
        "Before you run this: quit Obsidian, so the generated files install\n"
        "cleanly. Step 3 opens your vault in Obsidian itself and installs the\n"
        "plugins through its CLI. If that can't work on your setup, it prints\n"
        "the short manual path instead."
    )

    step(1, 3, "Creating your config")
    created = ensure_config()
    vault = resolve_vault(created)
    if not Path(vault).expanduser().is_dir():
        sys.exit(f"Not a directory: {vault}\n"
                 "(check the path in config.toml's [vault] section)")
    write_vault_path(vault)
    ask_preferences(created)

    step(2, 3, "Generating and installing vault files")
    ensure_tomli()
    run_generate(vault)

    step(3, 3, "Installing Obsidian plugins")
    install_plugins(vault)

    print(
        "\nAlmost there. Finish these in Obsidian (one-time, GUI only):\n"
        "  1. Restart Obsidian.\n"
        "  2. Dataview settings → enable 'JavaScript queries'.\n"
        "  3. Settings → Hotkeys → search 'QuickAdd' → assign hotkeys\n"
        "     (suggested: Cmd/Ctrl+Shift+L for LeetCode).\n"
        "Then open your dashboard note in Reading view and log your first entry."
    )


if __name__ == "__main__":
    main()