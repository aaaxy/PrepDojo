---
name: lc-logger
description: Log a LeetCode problem into the user's Obsidian interview-prep tracker (daily notes + Dataview dashboard). Trigger whenever the user pastes a leetcode.com problem URL — even with no other words — or says anything like "log this", "log this lc problem", "just did/solved a problem", "add two sum to my log", "did 239 today", or asks to backfill a solve for a past day ("log this for yesterday"). Also trigger for logging other prep categories into the same tracker (ML fundamentals reviewed, ML coding practice, system design, behavioral stories). Do NOT trigger when the user wants help solving a problem, explaining an algorithm, or changing the dashboard itself.
---

# LC Logger

Log solved LeetCode problems (and other interview-prep work) into the user's Obsidian vault, where a Dataview dashboard aggregates them. The user's priority is zero-friction logging: a bare URL means "log this for today" — don't ask questions unless something is truly ambiguous.

## Where things live

The Obsidian vault is the user's connected folder. Inside it:

- Daily notes: `@@DAILY_NOTES_FOLDER@@/@@DATE_FORMAT@@.md`
- Daily note template: `@@DAILY_NOTE_TEMPLATE@@`
- Dashboard (never edit when logging): `@@DASHBOARD_PATH@@`

## Entry format

Entries are plain bullets (no checkboxes — unchecked boxes are treated as placeholders and ignored by the dashboard) under the `@@PREP_HEADING@@` heading:

```
- LC #<number> <Canonical Title> · <@@DIFFICULTIES_PIPE@@> · <topic> #@@TAG_LC@@
```

Example: `- LC #200 Number of Islands · Medium · bfs/dfs #@@TAG_LC@@`

The ` · ` separators matter — the dashboard splits on them (problem · difficulty · topic).

**Topic must be one of** (lowercase, exact strings, so dashboard grouping stays consistent):
@@TOPICS_INLINE@@

Rules for topics — these keep the dashboard's grouping and the user's QuickAdd dropdown consistent:

- Always lowercase.
- Never invent a topic string outside this list. If the problem's natural tag isn't in the list (union find, trie, monotonic stack, math...), offer the closest taxonomy matches in the topic question and include the unmapped tag as an option too — let the user decide; their choice may legitimately extend their taxonomy.
- Finer divisions use `main - subtopic`, where `main` is a taxonomy item: `dp - knapsack`, `trees - bst`. The dashboard groups by the part before ` - `, so subtopics enrich rather than fragment the stats.
- If the user names a topic themselves, normalize it (lowercase, map "dynamic programming" → "dp") rather than writing a new variant.

## Identifying the problem

Users may give a URL (`leetcode.com/problems/<slug>/...`), a number ("did 239"), or a name ("just solved coin change"). From any of these, fill in the canonical number, title, and difficulty from your own knowledge — you know the LeetCode catalog well and this avoids a slow page fetch (LeetCode pages are JS-rendered and often fetch poorly anyway). Only if you're genuinely unsure (obscure or very recent problem) do a quick web search, and if still unsure, log what you have and tell the user which field to double-check rather than blocking.

## Confirming the topic

Many problems have several valid approaches (e.g., #416 can be seen as dp or backtracking), and the topic should record how the *user* solved it, not the textbook label. So unless the user already stated their approach in the message, ask before logging: take the problem's official topic tags, map them to the taxonomy above, and present them as options (put the most likely intended approach first, marked Recommended; 2-4 options). Use the AskUserQuestion tool if available so it renders as clickable choices.

Ask about topic and notes together in ONE AskUserQuestion call (two questions in the same dialog — never two separate rounds). If the user's message didn't mention any notes, the second question offers quick options like "No notes" (first/default), "Needed hints", "Second attempt", "Review again soon" — the built-in Other option covers free-text notes. Skip either question whose answer the user already gave in their message; if they gave both (approach and notes, or explicitly "no notes"), ask nothing and log immediately — don't add friction where there is none.

## Notes on a problem

If the user includes commentary, decide by length:

- Short remark ("needed hints", "second attempt", "review in a week"): append inline as a 4th segment before the tag — `- LC #322 Coin Change · Medium · dp · needed hints #@@TAG_LC@@`. This shows up in the dashboard's Notes column.
- Longer notes (an insight, a mistake analysis, complexity discussion): keep the entry line short and put the notes as indented sub-bullets under it. The dashboard intentionally ignores sub-bullets (they have no #@@TAG_LC@@ tag), so long notes live in the daily note without cluttering tables:

```
- LC #416 Partition Equal Subset Sum · Medium · dp #@@TAG_LC@@
    - key insight: reduces to subset-sum with target = total/2
    - got TLE with plain recursion, memoization fixed it
```

## Which day

Default to today. Respect phrases like "yesterday", "last friday", or explicit dates. Get today's date from the environment/bash, not from memory.

## Writing the entry

1. Open `@@DAILY_NOTES_FOLDER@@/<date>.md`. If it doesn't exist, create it from `@@DAILY_NOTE_TEMPLATE@@`, replacing `{{date}}` with `<date>` and `{{date:dddd, MMMM D, YYYY}}` with the long form (e.g., "Thursday, July 16, 2026").
2. Append the entry on its own line under `@@PREP_HEADING@@` (before the next heading of the same level).
3. Dedupe: if the same problem number is already logged that day, don't add it again — tell the user it's already there.
4. Confirm in one short line what was logged and to which date, e.g., "Logged: LC #239 Sliding Window Maximum · Hard · sliding window → 2026-07-16". No lengthy explanation.

## Other categories

If the user asks to log non-LC prep, same rules (plain bullet under `@@PREP_HEADING@@`, tag last):

- @@NAME_MLFUND@@: `- <topic> · <🟢|🟡|🔴> #@@TAG_MLFUND@@` (🟢 solid, 🟡 shaky, 🔴 needs re-review; ask for or infer confidence, default 🟢 if they say it went well)
- @@NAME_MLCODE@@: `- <what was implemented> #@@TAG_MLCODE@@`
- @@NAME_MLSYS@@: `- <case/question> #@@TAG_MLSYS@@`
- @@NAME_BQ@@: `- <story/question practiced> #@@TAG_BQ@@`
