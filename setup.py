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
    python3 setup.py
        First run: creates config.toml and tells you to put your vault path in
        it (edit the file in any text editor). Second run: installs everything.
    python3 setup.py /path/to/YourVault
        One-shot alternative: pass the vault path directly; it is recorded in
        config.toml for you. (PREPDOJO_VAULT env var works too.)

Requires Python 3.9+. On 3.9/3.10 it installs the `tomli` package for you;
on 3.11+ nothing extra is needed. Runs on macOS, Linux, and Windows.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
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


EDIT_INSTRUCTIONS = (
    '  In the [vault] section, find:   # path = "/absolute/path/to/YourVault"\n'
    '  Remove the leading "# " and put your vault\'s location between the\n'
    '  quotes, e.g.:   path = "~/Documents/MyVault"\n'
    "  (Tip: drag the vault folder into the editor line, or right-click the\n"
    "  folder → hold Option (macOS) → 'Copy as Pathname'.)\n"
    "  While you're in there: if you already keep daily notes in a specific\n"
    "  folder, set daily_notes_folder in the same section."
)


def open_in_editor(path: Path) -> bool:
    """Best-effort: open the file with the system default app."""
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        elif os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", str(path)], check=False,
                           stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


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

    # No path yet: open the config in the user's editor and wait, so setup
    # completes in this single run.
    cfg = ROOT / "config.toml"
    print("\nOne thing to fill in — your vault's location.")
    opened = open_in_editor(cfg)
    print(f"  {'Opening' if opened else 'Open'}  {cfg}  {'in your editor...' if opened else 'in any text editor.'}")
    print(EDIT_INSTRUCTIONS)
    while True:
        try:
            answer = input("\nSave the file, then press Enter to continue (or q to quit): ")
        except EOFError:
            # Non-interactive (CI, piped): fall back to the two-run flow.
            print("\nNo interactive terminal. Fill in the path as described above,")
            print("then run  python3 setup.py  again.")
            sys.exit(0)
        if answer.strip().lower() == "q":
            print("Stopped. Rerun  python3 setup.py  once the path is filled in.")
            sys.exit(0)
        from_config = config_vault_path()
        if from_config:
            print(f"  got it: {from_config}")
            return from_config
        print("  config.toml still has no vault path — check the [vault] section,")
        print('  make sure the line starts with  path = "  (no leading #), and save.')


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
    "    Settings → Community plugins → Browse → Dataview, QuickAdd, Calendar."
)


def active_vault(obsidian: str) -> Optional[str]:
    """Path of the vault Obsidian currently has open, or None if undeterminable.
    The CLI installs plugins into THIS vault — it can't target an arbitrary
    folder — so we use it to make sure we install into the right one."""
    result = subprocess.run(
        [obsidian, "vault", "info=path"], capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    # Output may carry Obsidian's own warning lines; the path is the last one.
    lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
    return lines[-1] if lines else None


def install_plugins(vault: str) -> None:
    obsidian = shutil.which("obsidian")
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
    current = active_vault(obsidian)
    if current is None or Path(current).resolve() != target:
        print(
            "  Skipping automatic plugin install. The Obsidian CLI installs into\n"
            "  the vault currently open in Obsidian, which isn't your target vault:\n"
            f"    open now: {current or 'unknown'}\n"
            f"    target:   {target}\n"
            "  Open your target vault in Obsidian, then rerun this script — or:\n"
            + MANUAL_PLUGINS
        )
        return

    # Community plugins can only be installed with Restricted Mode off.
    subprocess.run([obsidian, "plugins:restrict", "off"])
    failed = []
    for pid in PLUGINS:
        result = subprocess.run([obsidian, "plugin:install", f"id={pid}", "enable"])
        if result.returncode != 0:
            failed.append(pid)
    installed = [p for p in PLUGINS if p not in failed]
    if installed:
        print("  installed and enabled: " + ", ".join(installed))
    if failed:
        print("  could not install: " + ", ".join(failed)
              + " — add them by hand from Settings → Community plugins → Browse")


def main() -> None:
    if sys.version_info < (3, 9):
        sys.exit(
            f"PrepDojo needs Python 3.9+ (you have {sys.version.split()[0]}).\n"
            "Install a newer Python and run it explicitly, e.g. python3.11 setup.py ..."
        )

    print("PrepDojo setup")
    print("==============")
    print(
        "Before you run this: open your target vault in Obsidian at least once\n"
        "(so its CLI can install plugins into it), then quit Obsidian so the\n"
        "generated files install cleanly. Step 3 reopens Obsidian for the plugins.\n"
        "If the vault open in Obsidian isn't your target, step 3 safely skips and\n"
        "tells you how to finish."
    )

    step(1, 3, "Creating your config")
    created = ensure_config()
    vault = resolve_vault(created)
    if not Path(vault).expanduser().is_dir():
        sys.exit(f"Not a directory: {vault}\n"
                 "(check the path in config.toml's [vault] section)")
    write_vault_path(vault)

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