# Manual setup (no Python required)

This walkthrough recreates the whole system by hand. Wherever this guide says `Calendar/Daily Notes`, `## Interview Prep`, or a tag like `#lc`, you can substitute your own choice; just keep it consistent across all steps. If you run `generate.py` instead, all of this is done for you.

## 1. Install plugins

Settings → Community plugins → turn off Restricted mode → Browse. Install and enable:

- **Calendar** (by Liam Cain): month grid in the sidebar; click a date to open that day's note
- **Dataview** (by blacksmithgu): powers the dashboard. In its settings, enable **JavaScript queries**
- **QuickAdd** (by Christian B. B. Houmann): hotkey-driven logging prompts

## 2. Daily notes

1. Create your daily note template (copy `templates/vault/daily-note.md` from this repo into e.g. `Templates/Daily Note.md`, replacing `@@PREP_HEADING@@` with `## Interview Prep`).
2. Settings → Daily notes: set the new file location (e.g. `Calendar/Daily Notes`), date format `YYYY-MM-DD`, and the template file location.

## 3. Dashboard

Copy `templates/vault/dashboard.md` into your vault (e.g. as `Interview Prep Dashboard.md`) and replace every placeholder:

| Placeholder | Example value |
|---|---|
| `@@DAILY_NOTES_FOLDER@@` | `Calendar/Daily Notes` |
| `@@PREP_HEADING@@` | `## Interview Prep` |
| `@@TAG_LC@@` / `@@TAG_MLFUND@@` / `@@TAG_MLCODE@@` / `@@TAG_MLSYS@@` / `@@TAG_BQ@@` | `lc`, `mlfund`, `mlcode`, `mlsys`, `bq` |
| `@@NAME_LC@@` etc. | `LeetCode`, `ML Fundamentals`, ... |

Open the note in Reading view. Tables appear once you have logged entries.

## 4. QuickAdd captures

Settings → QuickAdd. For each category, type a name (e.g. `Log LC`), choose type **Capture**, click **Add Choice**, then open its ⚙️ settings:

- **Capture To**: `Calendar/Daily Notes/{{VDATE:Which day?,YYYY-MM-DD|today}}.md`
  (the `VDATE` prompt accepts natural language: today, yesterday, last friday, or aliases like `t`, `yd` configurable in QuickAdd's "Date aliases" setting)
- **Create file if it doesn't exist**: on, **Create file with given template**: your daily note template
- **Write position / Insert after**: on, set to `## Interview Prep`; enable "Create line if not found"
- **Task**: off (entries are plain bullets)
- **Capture format**: on. Paste the format for the category, and make sure the format ends with a newline (press Enter after the tag), otherwise consecutive entries merge onto one line:

LeetCode:

```
- LC {{VALUE:Problem name (e.g. #200 Number of Islands)}} · {{VALUE:Easy,Medium,Hard}} · {{VALUE:arrays & hashing,two pointers,sliding window,stack,binary search,linked list,trees,heap,backtracking,graphs,bfs/dfs,dp,greedy,intervals,bit manipulation}} #lc
```

ML fundamentals:

```
- {{VALUE:Topic reviewed}} · {{VALUE:🟢,🟡,🔴}} #mlfund
```

ML coding:

```
- {{VALUE:What did you implement?}} #mlcode
```

System design:

```
- {{VALUE:Design question or case}} #mlsys
```

Behavioral:

```
- {{VALUE:Story or question practiced}} #bq
```

A plain `{{VALUE:label}}` prompts for text with that label; a comma-separated `{{VALUE:a,b,c}}` renders a dropdown. Edit the topic list to taste; it is just that comma-separated string.

Finally, click the ⚡ (command) icon on each choice so it becomes assignable, then Settings → Hotkeys → search "QuickAdd" → assign (suggested: `Cmd/Ctrl+Shift+L` for LC, `Cmd/Ctrl+Shift+M` for ML fundamentals).

## 5. Claude skill (optional)

If you use Claude Cowork or Claude Code with your vault as a working folder, copy `templates/skill/SKILL.md`, replace the same placeholders as above (plus `@@DATE_FORMAT@@`, `@@DAILY_NOTE_TEMPLATE@@`, `@@DASHBOARD_PATH@@`, `@@TOPICS_INLINE@@`, `@@DIFFICULTIES_PIPE@@`), and install it as a skill named `lc-logger`. Then pasting a LeetCode link into a session is enough to log a problem.

## 6. Try it

Press your hotkey, log a problem for "today", then open the dashboard in Reading view. You should see the entry in every relevant table and a 1-day streak.
