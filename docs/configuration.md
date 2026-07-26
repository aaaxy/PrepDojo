# Configuration reference

`config.toml` only needs the settings you want to change; everything else
falls back to the defaults below. Add any setting from this page to your
`config.toml` (create the section header if it isn't there yet), then apply
it: quit Obsidian, run `python3 generate.py`, restart Obsidian.

The values shown are the defaults.

```toml
[vault]
# Absolute path to your Obsidian vault (setup.py records this for you).
path = "/absolute/path/to/YourVault"

# Where daily notes live, relative to the vault root.
daily_notes_folder = "Calendar/Daily Notes"

# Daily note filename format (moment.js syntax, used by Obsidian & QuickAdd).
date_format = "YYYY-MM-DD"

# Daily note template location, relative to the vault root.
daily_note_template = "Templates/Daily Note.md"

# Where the generated dashboard note goes, relative to the vault root.
dashboard_path = "Interview Prep Dashboard.md"

# The heading inside daily notes that entries are logged under.
prep_heading = "## Interview Prep"

# ------------------------------------------------------------
# Categories: name = how it appears on the dashboard,
# tag = the inline tag that marks an entry (no '#'),
# hotkey = QuickAdd hotkey (omit to leave unassigned;
# Mod = Cmd on macOS / Ctrl on Windows-Linux).
# Rename all five and the same system tracks any daily practice.
# ------------------------------------------------------------

[categories.lc]
name = "LeetCode"
tag = "lc"
hotkey = { modifiers = ["Mod", "Shift"], key = "L" }

[categories.mlfund]
name = "ML Fundamentals"
tag = "mlfund"
hotkey = { modifiers = ["Mod", "Shift"], key = "M" }

[categories.mlcode]
name = "ML Coding"
tag = "mlcode"

[categories.mlsys]
name = "ML System Design"
tag = "mlsys"
# Source types offered when logging (what kind of material it was).
sources = ["question", "blog", "video", "course", "paper", "project", "other"]

[categories.bq]
name = "Behavioral"
tag = "bq"

[categories.mock]
name = "Mock Interviews"
tag = "mock"
# Session types offered when logging.
types = ["coding", "behavioral", "system design"]

[leetcode]
# LeetCode username for the import (dashboard button and `prepdojo sync-lc`).
# Public profiles only. Unset = import disabled.
# username = "your-leetcode-username"

# Earliest date sync-lc will log entries for (avoids creating daily notes
# for old solves). Unset = last 7 days. "all" = backfill everything.
# sync_since = "2026-07-01"

difficulties = ["Easy", "Medium", "Hard"]

# Topic taxonomy for the dropdowns and dashboard grouping. Keep lowercase;
# finer divisions use "main - subtopic" (e.g. "dp - knapsack") and the
# dashboard groups them under "dp".
topics = [
  "arrays & hashing", "two pointers", "sliding window", "stack",
  "binary search", "linked list", "trees", "heap", "backtracking",
  "graphs", "bfs/dfs", "dp", "greedy", "intervals", "bit manipulation",
]

[applications]
# Folder inside the vault holding applications.csv and resume-versions.csv.
folder = "Applications"

# Hotkey for the in-Obsidian "Log Application" prompts.
hotkey = { modifiers = ["Mod", "Shift"], key = "A" }
```
