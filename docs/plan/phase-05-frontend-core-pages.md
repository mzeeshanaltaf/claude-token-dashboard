# Phase 05: Frontend core pages

**Goal:** build the redesigned versions of every page the old app has, so they're more appealing and easier to read: Overview, Prompts, Sessions (list plus a basic detail page), Projects (list plus detail), Skills, Tips and Settings. Every feature of the old UI must survive, **unless this file explicitly drops it**. The new features (Activity, Deep session view, Tools page, search, export) are phase 06.

## Entry criteria

- Phase 04 is `done`: the shell, login, proxy and formatting helpers work.

## Environment check

```bash
cd backend && uv run uvicorn claude_lens.api.main:app --port 8000
cd frontend && pnpm dev
```

## Read first

- Every file in `web/routes/` (the old pages): this is the feature inventory to preserve.
- The `dataviz` skill, **before writing any chart**.
- HANDOFF.md notes from phase 03 about the pagination envelopes.
- `frontend/README.md` § Conventions (written in phase 04): the API helpers, `useRangedQuery`, chart colour tokens and `blur-sensitive`. The pages replace `frontend/components/placeholders.tsx`.
- *(from phase 04)* `/api/daily` returns tokens only. The Est. cost sparkline needs a per-day `cost_usd` added to the backend first; then run `pnpm gen:api`.

## Tasks

### Overview (`/overview`)
- [ ] **Hero KPIs** (4 cards, each with a sparkline of the daily series):
  - Est. cost, with the plan note ("you pay $X/mo on Max", the old `planSubtitle`);
  - Sessions;
  - Prompts (turns);
  - **Cache hit rate** (new derived metric: `cache_read / (cache_read + input + cache_create)`).
- [ ] **Token composition bar:** one horizontal 100% bar with segments for input, output, cache read and cache create (5m and 1h shown in the tooltip). Each segment carries its token count and **cost**. This replaces the old five token KPI cards.
- [ ] **Daily chart:** a stacked bar or area chart with a **Tokens / Cost** toggle.
  - In Cost mode, it stacks by model family.
  - In Tokens mode, it stacks the core token types, and cache reads move to a separate small chart (they're about 100× larger, as in the old app).
- [ ] **Model mix:** a donut by family, with a list of versions beside it (share bar, tokens, cost). Clicking a family filters the list. This **replaces the sunburst**: keep the information, drop the zoom interaction.
- [ ] **Top projects by cost:** a horizontal bar with the share of spend; clicking a bar opens the project.
- [ ] **Top tools:** calls per tool (the top 8).
- [ ] **Recent sessions:** 10 rows linking to the session.
- [ ] Glossary: each term from the old "What do these numbers mean?" block becomes an **info tooltip** on its metric. Keep the definitions' wording.
- [ ] Mark project names, prompts and titles `.blur-sensitive`, including in chart axis labels and tooltips.

### Prompts (`/prompts`)
- [ ] A server-paginated table:
  - columns: time, project, prompt preview, model badge, core tokens, cache reads, **cost with an inline bar**;
  - sort by cost, tokens or recent;
  - filters for project and model; text search.
- [ ] Clicking a row opens a side **Sheet** with:
  - the full prompt (monospace, scrollable);
  - token and cost breakdown;
  - session title, linking to the session.

### Sessions (`/sessions`, `/sessions/[id]`)
- [ ] List: a TanStack Table with server-side sorting and pagination (page sizes 25/50/100/200).
  - Columns: started, project, title, turns, input, output, cache reads, cache writes (5m/1h in the tooltip), total tokens, cost.
  - Search box; project filter.
- [ ] Basic detail page (phase 06 enriches it):
  - header with title, project and the short session id;
  - KPI strip: started, ended, duration, records, cost;
  - token cards with cost;
  - the turn-by-turn table (time, type, sidechain badge, model badge, prompt/tool summary, in, out, cache rd, cache wr 5m, cache wr 1h), where clicking a row opens a dialog or sheet with the full prompt or tool calls (as the old modal does).

### Projects (`/projects`, `/projects/[slug]`)
- [ ] List: cards or a table with name, sessions, turns, cost, last active, and a sparkline of daily cost. Sortable.
  - Daily cost per project needs a small backend addition (`/api/projects?with_daily=1`, or a separate `/api/projects/daily`). Add it to the backend in this phase and note it in HANDOFF.md.
- [ ] Detail page:
  - KPIs with the cost breakdown (input, output, cache read, cache write);
  - daily cost chart and model mix for the project;
  - the project's sessions table.

### Skills (`/skills`)
- [ ] A bar chart of the top skills by invocations.
- [ ] A table: skill, invocations, sessions, last used, tokens per call. When `tokens_per_call` is null, show the "not installed in a scanned root" hint from `docs/KNOWN_LIMITATIONS.md`.

### Tips (`/tips`)
- [ ] Cards: a category icon (cache, repeat-file, repeat-bash, right-size, tool-bloat, subagent-outlier), title, body and a **Dismiss** button with an optimistic update and an undo toast.
- [ ] An empty state when there are no suggestions.

### Settings (`/settings`)
- [ ] Plan selector (api, pro, max, max-20x) and a timezone selector (defaulting to the browser's zone), both saved via the API.
- [ ] The pricing table, read-only, from `/api/plan` → `pricing`.
- [ ] Sync status: the last runs per machine, from `/api/sync-status`, with the `claude-lens scan` hint.
- [ ] A change-password form (current, new, confirm).
- [ ] An explanation of the privacy blur.

## Exit criteria

- `pnpm lint && pnpm build` pass.
- A side-by-side check against the old app (`python cli.py dashboard` on :8080) for `range=all`: Overview est. cost, sessions, turns and each token total match. Spot-check one project and one session. Record the numbers.
- Every old feature in `web/routes/*.js` is present, or listed in HANDOFF.md as intentionally changed (e.g. sunburst → donut).
- No hydration warnings. Usable at a 390px width (sidebar collapses to a sheet).

## Handoff notes to capture

- Any backend endpoints added or changed in this phase.
- The page and component patterns phase 06 should reuse.
