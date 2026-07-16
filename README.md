# Grindstone 🪨

*Keep your interview prep sharp.*

Grindstone is a **daily-practice tracking system** built on [Obsidian](https://obsidian.md). One hotkey or a pasted LeetCode link is a complete log entry; one note is your whole picture, with streaks, topic and difficulty breakdowns, and a "needs re-review" list, always current.

It ships as three coordinated layers, all generated from one config file:

- **Capture** — instant logging from anywhere: QuickAdd hotkey actions with dropdown prompts inside Obsidian, or an AI logging skill (built for Claude, portable to any LLM agent) that turns "just did two sum" or a pasted LeetCode URL into a correctly formatted entry
- **Storage** — entries are plain markdown bullets in your daily notes: human-readable, grep-able, no database, no lock-in
- **Insight** — a live Dataview dashboard computing streaks, per-topic and per-difficulty breakdowns, and a "needs re-review" list

The default configuration tracks ML engineer interview prep (LeetCode, ML fundamentals, ML coding, system design, behavioral), but nothing is hardcoded: categories, tags, topic taxonomies, folder layout, hotkeys, and formats all live in `config.toml`, and `generate.py` rebuilds every layer — Obsidian configs, QuickAdd actions, dashboard, and the AI skill — to match. Rename the categories and the same machinery tracks language learning, fitness, or any daily practice.

## System overview

Daily workflow, from a solved problem to insight:

```mermaid
flowchart LR
    subgraph capture ["⚡ Capture (seconds)"]
        subgraph obs ["inside Obsidian"]
            QA["QuickAdd hotkey<br/>labeled prompts + dropdowns"]
            MB["Manual bullet<br/>type it yourself"]
        end
        subgraph cl ["chat with Claude"]
            CS["lc-logger skill<br/>paste a link or say 'log it'"]
        end
    end
    subgraph storage ["📝 Storage (plain markdown)"]
        DN["Daily notes<br/><code>- LC #200 Number of Islands · Medium · bfs/dfs #lc</code>"]
    end
    subgraph insight ["📊 Insight (always current)"]
        DB["Dataview dashboard<br/>streaks · topic coverage · difficulty mix · needs re-review"]
    end
    QA --> DN
    CS --> DN
    MB --> DN
    DN --> DB
```

One-time setup, everything personalized from a single file:

```mermaid
flowchart LR
    CFG["config.toml<br/>paths · tags · categories<br/>topics · hotkeys"] --> GEN["generate.py"]
    GEN --> T["Daily note template"]
    GEN --> D["Dashboard note"]
    GEN --> Q["QuickAdd actions<br/>+ hotkey bindings"]
    GEN --> S["lc-logger<br/>Claude skill"]
    T & D & Q --> V["Your Obsidian vault"]
    S --> C["Your Claude setup"]
```

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

   Installs are edit-safe: grindstone keeps a checksum manifest (`.obsidian/grindstone-manifest.json`) of everything it installs. Files you've never touched are updated in place; files you've edited (or that grindstone didn't create) are left alone, and the fresh version lands next to them as `*.new.md` for manual merging. `--force` overwrites unconditionally. You can also install by hand:

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
- With other LLMs: the skill is plain markdown with every convention spelled out, so it doubles as a ready-made system prompt for any agent that can read and write files in your vault (a custom GPT, Cursor rules, a Gemini CLI context file, an `AGENTS.md`). Copy the contents of `dist/claude-skill/lc-logger/SKILL.md` into your agent's instructions; only the packaging and the clickable question dialog are Claude-specific, and the latter degrades gracefully to a plain-text question.
- By hand: type the bullet yourself. Unchecked checkboxes (`- [ ]`) are treated as placeholders and ignored by the dashboard; plain bullets and checked tasks count.

## Conventions worth knowing

- Topics are lowercase and come from the taxonomy in `config.toml`. Consistency is what makes the by-topic table useful.
- Finer divisions use `main - subtopic` (e.g. `dp - knapsack`); the dashboard groups them under `main` and shows the full string in the problem table.
- A short note can ride on the entry as a fourth segment (`... · dp · needed hints #lc`) and appears in the dashboard's Notes column. Longer notes go as indented sub-bullets under the entry; the dashboard ignores them on purpose.
- Difficulty accepts `Easy/Medium/Hard`, `E/M/H`, or 🟢/🟡/🔴; the dashboard normalizes all of them.

## Changing your configuration later

Generation is a build step, not a one-time event. When you edit `config.toml` (new topic, renamed category, different hotkey), rerun:

```bash
python3 generate.py --install /path/to/YourVault
```

and restart Obsidian. Three things to know:

1. Customize in the repo's `templates/`, not in the installed vault copies; treat the vault files as build outputs. If you do edit a vault copy, the checksum manifest protects it (see above), and you merge from the `*.new.md` file at your own pace.
2. Regenerate the QuickAdd config while Obsidian is closed. The plugin holds settings in memory and can write the old version back over your new file when it quits.
3. Config changes affect future entries only. If you rename a tag (say `lc` to `leetcode`), old entries still carry the old tag and will drop off the dashboard until you find-and-replace them in your daily notes.

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
