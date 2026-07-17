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
    python3 setup.py                      # prompts for the vault path (or uses
                                          # the PREPDOJO_VAULT env var)

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


def ensure_config() -> None:
    cfg = ROOT / "config.toml"
    template = ROOT / "config-template.toml"
    if cfg.exists():
        print("  config.toml already exists — leaving your settings untouched")
        return
    if not template.exists():
        sys.exit("  config-template.toml is missing; cannot create config.toml")
    cfg.write_bytes(template.read_bytes())
    print("  created config.toml from config-template.toml (using default paths)")
    print("  if you already keep daily notes in a specific folder, edit")
    print("  config.toml's [vault] section and rerun this script")


def resolve_vault() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    env = os.environ.get("PREPDOJO_VAULT")
    if env:
        print(f"  using PREPDOJO_VAULT: {env}")
        return env
    try:
        answer = input("  Path to your Obsidian vault: ").strip()
    except EOFError:
        answer = ""
    if not answer:
        sys.exit("  No vault path given. Rerun as: python3 setup.py /path/to/YourVault")
    return answer


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

    vault = resolve_vault()
    if not Path(vault).expanduser().is_dir():
        sys.exit(f"Not a directory: {vault}")

    step(1, 3, "Creating your config")
    ensure_config()

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