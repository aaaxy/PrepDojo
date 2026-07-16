# grindstone

*Keep your interview prep sharp.*

grindstone is a **daily-practice tracking framework** built on [Obsidian](https://obsidian.md). It ships as three coordinated layers, all generated from one config file:

- **Capture** — instant logging from anywhere: QuickAdd hotkey actions with dropdown prompts inside Obsidian, or an AI logging skill (Claude) that turns "just did two sum" or a pasted LeetCode URL into a correctly formatted entry
- **Storage** — entries are plain markdown bullets in your daily notes: human-readable, grep-able, no database, no lock-in
- **Insight** — a live Dataview dashboard computing streaks, per-topic and per-difficulty breakdowns, and a "needs re-review" list

The default configuration tracks ML engineer interview prep (LeetCode, ML fundamentals, ML coding, system design, behavioral), but nothing is hardcoded: categories, tags, topic taxonomies, folder layout, hotkeys, and formats all live in `config.toml`, and `generate.py` rebuilds every layer — Obsidian configs, QuickAdd actions, dashboard, and the AI skill — to match. Rename the categories and the same machinery tracks language learning, fitness, or any daily practice.

## How it works

Every entry is one plain bullet in a daily note, ending with a category tag:

```
## Interview Prep

- LC #200 Number of Islands · Medium · bfs/dfs #lc
- bias-variance tradeoff · 🟢 #mlfund
- design a feed ranking system #mlsys
```

That's the entire data model. Three tools write and read these lines:

1. **QuickAdd (Obsidian plugin)**: press a hotkey anywhere in Obsidian, pick a day ("today", "yesterday", "last friday"), fill labeled prompts with dropdowns for difficulty and topic. No typos, no format drift.
2. **Claude skill** (optional): paste a LeetCode URL into a Claude (Cowork/Claude Code) session with vault access and it identifies the problem, asks which approach you used, and writes the entry.
3. **Dashboard (Dataview)**: a single note that renders stats, streaks, and per-category tables from all daily notes. Open it; it is always current.

## Requirements

- Obsidian with community plugins: [Calendar](https://obsidian.md/plugins?id=calendar), [Dataview](https://obsidian.md/plugins?id=dataview) (enable "JavaScript queries" in its settings), [QuickAdd](https://obsidian.md/plugins?id=quickadd)
- Python 3.11+ to run the generator (or follow [manual setup](docs/manual-setup.md))
- Optional: Claude desktop app (Cowork) or Claude Code for the logging skill

## Quick start

1. Edit `config.toml`. Every knob lives there: folder paths, date format, tags, category names, hotkeys, the LeetCode topic taxonomy, and difficulty labels.
2. Generate:

   ```bash
   python3 generate.py
   ```

   Everything lands in `dist/`, personalized to your config.
3. Install into your vault, either automatically:

   ```bash
   python3 generate.py --install /path/to/YourVault
   ```

   (refuses to overwrite existing files unless you add `--force`), or by hand:

   | File in `dist/` | Where it goes |
   |---|---|
   | `vault/<your template path>` | same path inside your vault |
   | `vault/<your dashboard path>` | same path inside your vault |
   | `obsidian/daily-notes.json` | `<vault>/.obsidian/daily-notes.json` |
   | `obsidian/plugins/quickadd/data.json` | `<vault>/.obsidian/plugins/quickadd/data.json` (see warning below) |
   | `obsidian/hotkeys-snippet.json` | merge into `<vault>/.obsidian/hotkeys.json` |
   | `claude-skill/lc-logger.skill` | install in Claude (see below) |

4. Restart Obsidian so it picks up the config files.

> **Warning**: the generated QuickAdd `data.json` replaces the plugin's existing configuration. If you already use QuickAdd for other things, don't copy the file; instead recreate the five capture choices manually following [docs/manual-setup.md](docs/manual-setup.md).

## Logging

- In Obsidian: hotkey (default `Cmd/Ctrl+Shift+L` for LeetCode, `Cmd/Ctrl+Shift+M` for ML fundamentals) → pick day → answer prompts. The other three categories get QuickAdd choices too; assign hotkeys in `config.toml` or via Settings → Hotkeys.
- With Claude: install `dist/claude-skill/lc-logger.skill`, connect your vault folder to the session, then paste a problem link or say "did 239 yesterday, solved with dp".
- By hand: type the bullet yourself. Unchecked checkboxes (`- [ ]`) are treated as placeholders and ignored by the dashboard; plain bullets and checked tasks count.

## Conventions worth knowing

- Topics are lowercase and come from the taxonomy in `config.toml`. Consistency is what makes the by-topic table useful.
- Finer divisions use `main - subtopic` (e.g. `dp - knapsack`); the dashboard groups them under `main` and shows the full string in the problem table.
- A short note can ride on the entry as a fourth segment (`... · dp · needed hints #lc`) and appears in the dashboard's Notes column. Longer notes go as indented sub-bullets under the entry; the dashboard ignores them on purpose.
- Difficulty accepts `Easy/Medium/Hard`, `E/M/H`, or 🟢/🟡/🔴; the dashboard normalizes all of them.

## Repository layout

```
config.toml          all user configuration
generate.py          renders templates + builds plugin configs from config.toml
templates/
  vault/             daily note template and dashboard (with placeholders)
  skill/             Claude skill (with placeholders)
docs/manual-setup.md fully manual, no-Python setup walkthrough
dist/                generated output (gitignored)
```

## License

MIT. See [LICENSE](LICENSE).
