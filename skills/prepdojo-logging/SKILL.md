---
name: prepdojo-logging
description: Log interview-prep work into the user's PrepDojo-enabled Obsidian vault (daily notes read by a Dataview dashboard). Trigger whenever the user pastes a leetcode.com problem URL — even with no other words — or says anything like "log this", "log this lc problem", "just did/solved a problem", "add two sum to my log", "did 239 today", or asks to backfill a solve for a past day ("log this for yesterday"). Also trigger for logging the other prep categories PrepDojo tracks — ML fundamentals reviewed, ML coding practice, ML system design study, behavioral stories, and mock interviews. Do NOT trigger when the user wants help solving a problem, explaining an algorithm, or changing the dashboard itself. For bulk history import ("sync my leetcode"), don't import — see the "Out of scope" section.
---

# PrepDojo Logging

Log solved LeetCode problems and other interview-prep work into the user's Obsidian vault, where a Dataview dashboard aggregates them. The user's priority is zero-friction logging: a bare URL means "log this for today" — don't ask questions unless something is truly ambiguous.

This skill is generic: every path, tag, and taxonomy comes from the user's own `prepdojo.json`, never from this file.

## Find the vault, read the config (once per session)

All personalization lives in `prepdojo.json` at the user's vault root, written by PrepDojo's `generate.py`. Locate it ONCE per session, in this order, stopping at the first success:

1. **Pointer file.** Read `~/.claude/prepdojo-vault.json` (shape: `{"vault_path": "..."}`). If `<vault_path>/prepdojo.json` exists and parses, use it.
2. **Working folder.** Check the current working folder for `prepdojo.json`, then each parent up to three levels.
3. **Shallow search.** Search the session's accessible folders (connected/mounted folders, uploaded folders) for `prepdojo.json`, depth-limited (e.g. `find <root> -maxdepth 3 -name prepdojo.json -not -path '*/.*'`). Exactly one hit: use it silently. Several hits: ask the user which vault they mean.
4. **Ask.** If nothing is found, ask the user where their vault is — they may need to connect the folder to the session. Never guess, and never create a `prepdojo.json` yourself; only `generate.py` writes it.

After locating via steps 2–4, write the pointer file (create `~/.claude/` if needed) so future sessions skip the search. Best effort: if the write fails, continue without it.

Read `prepdojo.json` once and keep its values in mind for the whole session; do not re-read it for every entry. Its `vault` section gives the daily-notes folder, date format, daily-note template, dashboard path, and prep heading. `categories` gives each category's display name and tag. `leetcode` gives the difficulty labels and the topic taxonomy. If the vault folder is mounted read-only in this environment (e.g. a staged copy), write changes back through the platform's write-back mechanism rather than editing the staged copy.

Below, `config.X.Y` means the value at that path in `prepdojo.json`.

## Entry format

Entries are plain bullets (no checkboxes — unchecked boxes are treated as placeholders and ignored by the dashboard) under the `config.vault.prep_heading` heading:

```
- LC #<number> <Canonical Title> · <difficulty> · <topic> #<config.categories.lc.tag>
```

Example with the default tag: `- LC #200 Number of Islands · Medium · bfs/dfs #lc`

The ` · ` separators matter — the dashboard splits on them (problem · difficulty · topic). Because `·` is the field separator, it can never appear inside a field: replace any `·` in user-supplied text with `-`. Difficulty must be one of `config.leetcode.difficulties`.

**Topic must come from `config.leetcode.topics`** (lowercase, exact strings, so dashboard grouping stays consistent):

- Always lowercase.
- Never invent a topic string outside the list. If the problem's natural tag isn't in the taxonomy (union find, trie, monotonic stack, math...), offer the closest taxonomy matches in the topic question and include the unmapped tag as an option too — let the user decide; their choice may legitimately extend their taxonomy.
- Finer divisions use `main - subtopic`, where `main` is a taxonomy item: `dp - knapsack`, `trees - bst`. The dashboard groups by the part before ` - `, so subtopics enrich rather than fragment the stats.
- If the user names a topic themselves, normalize it (lowercase, map "dynamic programming" → "dp") rather than writing a new variant.

## Identifying the problem

Users may give a URL (`leetcode.com/problems/<slug>/...`), a number ("did 239"), or a name ("just solved coin change"). From any of these, fill in the canonical number, title, and difficulty from your own knowledge — you know the LeetCode catalog well and this avoids a slow page fetch (LeetCode pages are JS-rendered and often fetch poorly anyway). Only if you're genuinely unsure (obscure or very recent problem) do a quick web search, and if still unsure, log what you have and tell the user which field to double-check rather than blocking.

## Confirming the topic

Many problems have several valid approaches (e.g., #416 can be seen as dp or backtracking), and the topic should record how the *user* solved it, not the textbook label. So unless the user already stated their approach in the message, ask before logging: take the problem's official topic tags, map them to the user's taxonomy, and present them as options (put the most likely intended approach first, marked Recommended; 2-4 options). Use the AskUserQuestion tool if available so it renders as clickable choices.

Ask about topic and notes together in ONE AskUserQuestion call (two questions in the same dialog — never two separate rounds). If the user's message didn't mention any notes, the second question offers quick options like "No notes" (first/default), "Needed hints", "Second attempt", "Review again soon" — the built-in Other option covers free-text notes. Skip either question whose answer the user already gave in their message; if they gave both (approach and notes, or explicitly "no notes"), ask nothing and log immediately — don't add friction where there is none.

## Notes on a problem

If the user includes commentary, decide by length:

- Short remark ("needed hints", "second attempt", "review in a week"): append inline as a 4th segment before the tag — `- LC #322 Coin Change · Medium · dp · needed hints #lc`. This shows up in the dashboard's Notes column. Sanitize `·` to `-` inside the remark.
- Longer notes (an insight, a mistake analysis, complexity discussion): keep the entry line short and put the notes as indented sub-bullets under it. The dashboard intentionally ignores sub-bullets (they carry no tag), so long notes live in the daily note without cluttering tables:

```
- LC #416 Partition Equal Subset Sum · Medium · dp #lc
    - key insight: reduces to subset-sum with target = total/2
    - got TLE with plain recursion, memoization fixed it
```

## Which day

Default to today. Respect phrases like "yesterday", "last friday", or explicit dates. **Today means the user's local date.** Take it from the conversation context (the host injects the user's current date); do not compute it by running `date` in a sandboxed shell — sandbox timezones can differ from the user's, and an evening session would then log into tomorrow's note. If the context gives no date, ask the user instead of guessing.

## Writing the entry

1. Open `<config.vault.daily_notes_folder>/<date formatted per config.vault.date_format>.md`. If it doesn't exist, create it from the template at `config.vault.daily_note_template`, replacing `{{date}}` with the date and `{{date:dddd, MMMM D, YYYY}}` with the long form (e.g., "Thursday, July 16, 2026").
2. Append the entry on its own line under `config.vault.prep_heading` (before the next heading of the same level).
3. Dedupe: if the same problem number is already logged that day, don't add it again — tell the user it's already there.
4. Confirm in one short line what was logged and to which date, e.g., "Logged: LC #239 Sliding Window Maximum · Hard · sliding window → 2026-07-16". No lengthy explanation.

Never edit the dashboard note (`config.vault.dashboard_path`) when logging — it computes everything live from the entries. Never modify or delete existing entries unless the user explicitly asks.

## Other categories

Same rules for non-LC prep (plain bullet under the prep heading, tag last, ` · ` as separator, `·` sanitized out of field values, same-day dedupe on an identical line). Tags below are the config defaults; always use the actual `config.categories.<key>.tag`:

- **ML fundamentals** (`mlfund`): `- <topic> · <🟢|🟡|🔴> #mlfund` — 🟢 solid, 🟡 shaky, 🔴 needs re-review; ask for or infer confidence, default 🟢 if they say it went well.
- **ML coding** (`mlcode`): `- <what was implemented> #mlcode`
- **ML system design** (`mlsys`): `- <what> · <topic> · <source> · <link> · <notes> #mlsys` — every field after `<what>` is optional; omit empty fields entirely (no `· ·` litter). `<source>` must come from `config.categories.mlsys.sources`; links start with http.
- **Behavioral** (`bq`): `- <story/question practiced> #bq`
- **Mock interviews** (`mock`): `- <session: who/where> · <type> · <notes> #mock` — `<type>` must come from `config.categories.mock.types`; notes optional, omitted when empty.

## Out of scope

- **"Sync/import my leetcode history"**: don't fetch from LeetCode yourself — the import has one implementation, in PrepDojo's CLI, and duplicating it here would drift. If `config.leetcode.import_configured` is true, point the user to the dashboard's ⟳ Import button or `prepdojo sync-lc` in the repo. If false, tell them to set their LeetCode username in the repo's `config.toml` and rerun `python3 generate.py` to enable it.
- **Dashboard changes, taxonomy edits, config changes**: those belong in the PrepDojo repo's `config.toml` (then `python3 generate.py`), not in ad-hoc edits.
