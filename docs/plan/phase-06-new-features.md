# Phase 06: New features

**Goal:** add the three feature sets the user picked, backend and frontend for each:
1. **Activity insights**
2. **Deep session view**
3. **Search & export**

Also add the **Tools** page, which uses the same tool and file data as the deep session view.

## Entry criteria

- Phase 05 is `done`: the core pages are at parity with the old app.

## Environment check

```bash
cd backend && uv run pytest
cd frontend && pnpm build
```

## Read first

- `backend/claude_lens/db/migrations/001_init.sql`: the columns available (`git_branch`, `is_sidechain`, `agent_id`, `tool_calls_json`, `tool_calls.target`, `tool_use_id`, `is_error`, `prompt_tsv`)
- `backend/claude_lens/collector/parse.py`: `_TARGET_FIELDS`, i.e. which tool stores what in `target` (Task stores `subagent_type`)
- The `dataviz` skill
- `frontend/README.md` § Page patterns (written in phase 05): URL state, `DataTable`, filters, the chart components and their data helpers.

**Notes from phase 05** (they override the tasks below where they conflict):
- Per-day cost already exists: `/api/daily` rows carry `cost_usd`, `cost_by_model`, `sessions` and `turns`, built by `analytics.daily_model_tokens` + `core.costs.cost_by_model_per_key`. Reuse them for `/api/activity/calendar` instead of a second cost rollup.
- **A calendar-day link is `/sessions?since=<day>&until=<day>`.** The frontend's custom-range `until` is an **inclusive** local day (phase 04); `rangeToApi()` adds the day itself. `until=<day+1>` would show two days.
- The session page's turn table (`components/sessions/session-detail.tsx`) is client-paginated (100 rows) and defaults to **Turns** (prompts + assistant turns; tool-result/attachment records behind "All records"). "Scroll to that turn" must switch to the right page (and filter) first.
- `/tools` and `/activity` still render `components/placeholders.tsx`; delete that file when both are built.

## 1. Activity insights (`/activity`)

**Backend** (`db/queries/activity.py`, `api/routers/activity.py`). Every bucket uses the timezone from `settings`.
- [x] `GET /api/activity/calendar?metric=cost|tokens&days=365`: one value per local date. Compute cost per (day, model) with `cost_for`, then sum per day.
- [x] `GET /api/activity/hourly?since&until`: a 7×24 grid (ISO weekday × local hour) of turns, core tokens and cost.
- [x] `GET /api/activity/summary?since&until`:
  - active days; current and longest **streak** of consecutive active days;
  - busiest day (date plus cost);
  - average cost and tokens per active day;
  - most active project; most active hour.

**Frontend**
- [x] A GitHub-style **calendar heatmap**, built as a CSS grid of weeks × weekdays with a quantised colour scale, month labels, a tooltip showing the date, cost, tokens and sessions, and a cost/tokens toggle. Clicking a day opens `/sessions?since=<day>&until=<day+1>`.
- [x] An **hour × weekday heatmap**.
- [x] A row of summary KPI cards: streaks, busiest day, average per active day, top project, peak hour.

## 2. Deep session view (enrich `/sessions/[id]`)

**Backend:** `GET /api/sessions/{id}/insights` returns:
- [x] `context_growth`: for each assistant turn in order, `{ts, context_tokens: input+cache_read+cache_create, output_tokens, cost, model, is_sidechain}`.
- [x] `tool_timeline`: tool_use rows in order, each `{ts, tool_name, target, is_error}`. `is_error` comes from the matching `_tool_result` row via `tool_use_id`, and is null for migrated rows that have no `tool_use_id`.
- [x] `subagents`: sidechain messages grouped by `agent_id`, each `{agent_id, turns, tokens, cost, first_ts, last_ts}`, plus the Task invocations, each `{ts, subagent_type}`.
- [x] `files`: Read, Edit and Write targets with a count per action, sorted by total.
- [x] `branches` (distinct `git_branch`), `models` (per model: turns and cost) and `duration_s`.

**Frontend**
- [x] Header chips: git branch, duration, models.
- [x] A **context-growth line chart**: context size per assistant turn, with output tokens on a secondary bar series and sidechain turns marked. It shows when the context filled up and when compaction happened.
- [x] **Cost per turn** bars, so expensive turns stand out. Clicking a bar scrolls to that turn in the table.
- [x] A **tool timeline**: a compact swimlane of tool calls over time, coloured by tool, with errors in red.
- [x] A **subagents** card (table plus share of the session's cost) and a **files touched** card (top 15, with Read/Edit/Write counts).

## 3. Tools page (`/tools`)

- [x] `GET /api/tools/insights?since&until` returns:
  - tools: calls, result tokens and error rate (only rows with a `tool_use_id` count toward the rate, and the response says so);
  - the top 20 files (Read/Edit/Write counts);
  - the top 20 bash commands;
  - the top WebFetch domains.
- [x] The page: a calls-by-tool bar chart, a result-tokens-by-tool bar chart, an error-rate table, a top-files table and a top-commands table. Files and commands are `.blur-sensitive`.

## 4. Search & export

- [x] `GET /api/search?q=&limit=` returns grouped results:
  - `prompts`: `prompt_tsv @@ websearch_to_tsquery('english', q)`, ranked by `ts_rank`, with a `ts_headline` snippet;
  - `sessions`: title ILIKE;
  - `projects`: name or slug ILIKE.
  Use at most 8 of each.
- [x] Frontend: wire the **Cmd+K** command dialog from phase 04. Debounce at 200ms, show the groups, open a prompt in its session, and include keyboard navigation (built into shadcn Command). Blur the snippets when privacy is on.
- [x] `GET /api/export/{sessions|prompts|projects}.csv`:
  - accepts the same filters as the list endpoints;
  - streams via `StreamingResponse` with the stdlib `csv` module;
  - `Content-Disposition: attachment; filename=claude-lens-<table>-<date>.csv`;
  - no pagination cap (stream all matching rows).
- [x] An **Export CSV** button on the Sessions, Prompts and Projects tables that passes the current filters. Confirm the phase 04 proxy streams the download.

## Tests

- [x] Backend tests for the calendar (timezone bucketing across a UTC midnight), the streak calculation, the insights shapes, a search that matches a fixture prompt, and a CSV header and row count.

## Exit criteria

- `uv run pytest` and `pnpm lint && pnpm build` are green.
- Manual checks on real data:
  - the calendar shows the history going back to 2026-02;
  - a long session shows its context-growth curve and subagents;
  - Cmd+K finds a known prompt;
  - CSV export opens in Excel with the correct row count.
- No hydration warnings.

## Handoff notes to capture

- Query performance on real data (slow endpoints, indexes added).
- What fraction of tool rows have a `tool_use_id`. If it's low, recommend running `claude-lens scan --full` once.

## Outcome

Done 2026-11-22. All four feature sets are built, backend and frontend. The new endpoints are `activity/{calendar,hourly,summary}`, `sessions/{id}/insights`, `tools/insights`, `search` and `export/{sessions,prompts,projects}.csv`. The full backend suite passes, and `pnpm lint` / `pnpm build` are clean. 32/32 browser checks passed on a copy of the real data, with no hydration warnings. Excel row counts equal the API totals (1,090 / 69 / 27). Deviations are recorded in HANDOFF.md: output tokens get their own chart instead of a second axis, `Agent`/`PowerShell` targets are now collected, the calendar starts weeks on Monday, and the CSV cell cap is set for Excel.
