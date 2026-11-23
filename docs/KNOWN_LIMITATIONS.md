# Known Limitations

None of these are blockers. They're the rough edges you'll notice if you look hard.

## The data is only as fresh as the last sync

The dashboard runs on the VPS, but the transcripts live on your PC. The collector pushes them to Postgres when it runs: once a day from the `Claude Lens - Daily Sync` scheduled task (13:00 by default, or as soon as the PC is back on), or whenever you run `claude-lens scan` by hand. Anything you did since then isn't in the dashboard yet. The "Synced" badge in the top bar shows when the last successful sync finished, and Settings lists the recent runs per machine.

## Skills token counts come from the uploaded catalog

The Skills page shows every skill Claude Code invoked, how often, across how many sessions and when. The **tokens per call** column comes from the skill catalog the collector uploads on every scan: the size of each `SKILL.md` it finds under `~/.claude/skills/`, `~/.claude/scheduled-tasks/` and `~/.claude/plugins/` **on the machine that ran the scan** (an estimate of chars ÷ 4). Skills that live elsewhere (project-local `.claude/skills/`, skills dispatched through a subagent, or skills you've since deleted) show invocation counts with "not scanned" in the token column.

## `tool_use_id` is null for migrated rows

Tool errors, result tokens per tool and the subagent type of `Agent` calls need each tool call linked to its result by `tool_use_id`. The old Token Dashboard never stored it, so rows copied from its SQLite file don't have one. A `claude-lens scan --full` re-reads every transcript still on disk and links those calls (it was run on 2026-11-22: 84.8% of tool calls are now linked). Calls from transcripts Claude Code has already deleted stay unlinked, and the Tools page and the session view say how many calls their error figures cover.

## Cost for Pro / Max users is API-equivalent

Settings lets you pick your plan, but cost figures are always API-equivalent: what the same usage would cost at pay-per-token rates. On Pro you pay a flat $20/month however large that number gets. The Overview notes what you pay on your plan, but there's no "subscription value" maths: Anthropic doesn't publish per-plan limits in a form we could use.

## Cowork sessions are invisible

Claude's Cowork mode runs server-side and doesn't write JSONL to `~/.claude/projects/`, so the collector can't see it.

## Unknown model names get tier-fallback pricing

If a transcript references a model ID that isn't in `backend/pricing.json` (a new snapshot, say), its cost is estimated from the tier substring (`opus` / `sonnet` / `haiku`) in the name and marked as estimated. A name with none of those substrings has no cost. Add the model to `pricing.json`; the API reloads it when the file changes (in production, that means a redeploy).

## Day and hour buckets follow the timezone setting

Daily charts, the Activity calendar and the hour × weekday grid bucket by the `timezone` setting, which is `UTC` until you change it in Settings ("Use this browser's zone"). The Activity page shows which zone it uses.

## The first sync is slow over the network

The collector talks to Postgres on the VPS directly. A first `claude-lens scan` (or `--full`) over thousands of transcripts takes minutes, because every batch pays a ~150 ms round-trip. Later scans are incremental (per-file mtime + byte offset), so they only read new lines.
