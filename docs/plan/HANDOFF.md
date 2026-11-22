# Claude Lens: session handoff

The living state of the redesign. Read it at the **start** of every session, after `README.md`, and update it at the **end** of every session. The protocol is in [README.md § Session handoff protocol](README.md#session-handoff-protocol).

## Phase status

| # | Phase | Status | Started | Finished | Notes |
|---|---|---|---|---|---|
| 00 | Repo hygiene & backend scaffold | done | 2026-11-22 | 2026-11-22 | 71 backend tests pass |
| 01 | Postgres schema & batched collector | done | 2026-11-22 | 2026-11-22 | 129 backend tests pass (43 on Postgres); SQLite parity exact on a real project |
| 02 | SQLite migration & daily sync task | done | 2026-11-22 | 2026-11-22 | parity ok (30/30); daily task live, run #2 ok; 145 backend tests |
| 03 | FastAPI API & auth | done | 2026-11-22 | 2026-11-22 | 235 backend tests; overview totals = old app exactly ($6,438.7082) |
| 04 | Frontend shell & login | done | 2026-11-22 | 2026-11-22 | lint + build clean; 26/26 browser checks, no hydration warnings |
| 05 | Frontend core pages | done | 2026-11-22 | 2026-11-22 | lint + build clean; old vs new match exactly at a common cutoff; 25/25 browser checks |
| 06 | New features | done | 2026-11-22 | 2026-11-22 | 265 backend tests; lint + build clean; 32/32 browser checks; CSV rows = API = Excel |
| 07 | Deployment, docs & cleanup | not-started | | | |

Status values: `not-started` · `in-progress` · `blocked` · `done`

## Baton (replace this section at the end of every session)

- **Current phase:** 06 is done. Next is 07.
- **Last commit:** `4540d78 feat: activity insights, deep session view, tools page, cmd+k search and csv export` (phase 06), pushed to `mzeeshanaltaf/main`, plus a docs follow-up that records this hash.
- **What works:**
  - every page is real now (no placeholders): Activity (KPI cards, 12-month calendar heatmap, hour × weekday heatmap), Tools (calls / result tokens / errors by tool, top files, commands, WebFetch domains), the deep session view (header chips, context growth, cost per turn, tool timeline, subagents, files touched, click-to-turn), Cmd+K search, and CSV export on Sessions / Prompts / Projects;
  - the new endpoints (see Decisions and `backend/README.md` § API); the full backend suite, `pnpm lint` and `pnpm build` are green; the old app is untouched (85 tests OK).
- **What doesn't / open issues:**
  - **only 0.26% of tool rows have a `tool_use_id`** (175 of 66,884 tool_use rows; the rest were migrated from SQLite). So tool error rates, result tokens by tool and the timeline's red error marks cover only those calls (the UI says so), and `Agent` calls show "not recorded" for their subagent type. **Recommended: run `uv run claude-lens scan --full` once** (from `backend/`; idempotent). It re-reads the 1,205 transcripts still on disk; rows from the 75 deleted files stay as they are. It wasn't run here because it writes to the real schema; the user should decide;
  - carried over: `sync_runs` stays `running` after the final retry fails (phase 01); `core/names.py` slug walk-up rarely matches on this PC (phase 00/03); the first-run plan dialog is still unseen live; the sidebar's collapsed state isn't remembered;
  - **the real `timezone` setting is still `UTC`**, so the Activity buckets (and daily charts) are UTC days and hours. The page says so and links to Settings, which has a one-click "Use this browser's zone" (the user is in Asia/Karachi); the user should decide;
  - `/api/prompts` lists 493 prompts for all time (the old app's "prompt with an answering assistant row" rule); unchanged.
- **Exact next step:** start phase 07 with `phase-07-deployment-docs-and-cleanup.md`. Ask for the domain first, and read its new "(from phase 06)" notes (CSV streaming through Coolify's proxy, `node .next/standalone/server.js`, the scan `--full` question).

## Environment facts

Add facts as you learn them. Never record secrets.

- `DATABASE_URL` is in `.env.local` at the repo root. The target schema is `claude_dashboard`.
- Python 3.12.7, uv 0.8.3, Node 24.12, pnpm 10.5 on the Windows PC.
- Old SQLite: `~/.claude/token-dashboard.db`. Transcripts: `~/.claude/projects`.
- ~~The old scheduled task is named `Claude Token Dashboard - Daily Scan`.~~ It was removed in phase 02. The task is now **`Claude Lens - Daily Sync`**: daily at 13:00, running `backend\.venv\Scripts\pythonw.exe -m claude_lens.cli scan` in the repo root. Its log is `~/.claude/claude-lens-sync.log`; override the path with `CLAUDE_LENS_SYNC_LOG`.
- The real `claude_dashboard` schema was created on 2026-11-22 (migration 001) and seeded from SQLite with `machine = 'Zeeshan-Desktop'`. `settings` holds `plan` as the jsonb string `"pro"`.
- Migration timing over the network: 54.5 s in total (messages 28.9 s, tool_calls 10.6 s, the other tables under 1 s each).
- SQLite sha256 before and after phase 02: `4aa2a4c3…ee6a`, mtime 2026-11-21 13:00:02, 268,472,320 bytes. Unchanged.
- **`python3` doesn't work on this PC** (it's a Windows Store alias stub). Use `python` (3.12.7) for the old suite: `python -m unittest discover tests`. The old suite has **85** tests, not 68.
- Backend deps resolved by uv on 2026-11-22 (in `backend/uv.lock`):
  - runtime: fastapi 0.165.0, psycopg[binary] 3.3.9, psycopg-pool 3.3.3, pwdlib[argon2] 0.4.2, pydantic 2.14.4 (pydantic-core 2.50.5), uvicorn[standard] 0.54.0, starlette 1.10.0;
  - dev: pytest 9.2.0, httpx 0.28.1.
- `uvicorn[standard]` pulls in `python-dotenv` transitively. We don't use it; `config.py` has its own stdlib loader.
- The machine label default (`socket.gethostname()`) on this PC is `Zeeshan-Desktop`.
- Postgres server is **17** (`server_version_num` 170007). From the PC, a round-trip is **~150 ms** and a new connection takes **~1 s**.
- `TEST_DATABASE_URL` (optional) is used by the backend tests before `DATABASE_URL`. It's listed in `.env.example`.
- The skill catalog on this PC is **570 slugs**.
- **API (phase 03):** `uv run uvicorn claude_lens.api.main:app --port 8000` from `backend/`. Env var names: `ADMIN_USERNAME`, `ADMIN_PASSWORD` (only read while `users` is empty), `COOKIE_SECURE` (`false` for local http), `TRUST_PROXY`. The pool is min 1, max 10, and its sessions run in UTC.
- On this PC an authenticated API request costs ~0.5–1 s (3–6 round-trips at ~150 ms). On the VPS it will be local.
- FastAPI 0.165 ships an OpenTelemetry hook (`fastapi/telemetry`). It uses no-op providers unless `FASTAPI_OTEL_AUTO_CONFIGURE=true`, so nothing is exported by default. Don't set that variable.
- `starlette.testclient` warns that `httpx` is deprecated in favour of `httpx2`. Harmless for now.
- The full backend suite takes **~10 min** over the network. Teardown has been fixed (see Decisions), but check `pg_namespace` for stray `claude_lens_test_%` schemas if a run dies.
- SQLite `files.path` strings are exactly `str(Path)` of the `rglob` under `~/.claude/projects` (for example `C:\Users\…\.claude\projects\<slug>\<id>.jsonl`), the same as the new collector produces. Checked on 2026-11-22 against the live SQLite: with its offsets seeded, the collector would **skip 1,202** files, **rescan 3** (they changed since the last old-app scan) and find **75 missing**.
- **Frontend (phase 04):** `frontend/` is a pnpm project (`packageManager: pnpm@10.5.2`).
  - Installed on 2026-11-22: next 16.4.6, react / react-dom 19.3.0, radix-ui 1.8.1, shadcn CLI 4.23.0 (style `radix-nova`, icons `lucide-react` 1.77), tailwindcss 4.3.3 (via the `@tailwindcss/turbopack` loader), @tanstack/react-query 5.108.2, next-themes 0.4.6, recharts 3.8.0, react-day-picker 10, date-fns 4, sonner 2, cmdk 1.1, typescript 5.9.3, openapi-typescript 7.13.0, server-only.
  - **`cn` (0.5.2) is shadcn's own package** (repo `shadcn-ui/cn`), a compiled replacement for clsx + tailwind-merge. shadcn 4.x components import `cn` from `"cn"`, and `lib/utils.ts` re-exports it. It isn't a typo, so don't swap it out.
  - Next 16 scaffolds with `cacheComponents: true` + `partialPrefetching: true`; both are kept. Middleware is now **`proxy.ts`**, and the dev server writes `frontend/AGENTS.md` (keep it).
  - Next's docs ship in `frontend/node_modules/next/dist/docs/`. Read them before using an unfamiliar API: this version differs from older training data.
  - `next/font/google` (IBM Plex Sans, JetBrains Mono) downloads the fonts **at build time**, so the Docker build needs network access.
  - Dev: `pnpm dev` on :3000. Next reads env from `frontend/.env*`, not the repo root. `BACKEND_URL` defaults to `http://localhost:8000`, so local dev needs no env file.
  - Headless browser checks: the system Chrome (`C:/Program Files/Google/Chrome/Application/chrome.exe`) works with `playwright-core`, installed in the session scratchpad and not added to the project.
- **Frontend (phase 05):** added `@tanstack/react-table` **8.21.3** (pinned to v8; `latest` is 9.3.1 with a different API). No other new dependencies.
  - **Only one `next dev` can run per project directory** ("Another next dev server is already running"). To check against a second backend, use `pnpm build` and then `BACKEND_URL=http://localhost:<port> pnpm exec next start --port 3001`. A build doesn't disturb a running dev server.
  - **Git Bash rewrites `/overview`-style CLI arguments into Windows paths.** Prefix with `MSYS_NO_PATHCONV=1` when you pass routes to a script.
  - **`uvicorn --reload` on Windows can hang mid-reload** and leave an orphaned `multiprocessing.spawn` worker that keeps the port. Find it by `ParentProcessId` and `taskkill /T /F` it. Prefer restarting without `--reload`.
  - **Excel is installed** and scriptable via COM (`New-Object -ComObject Excel.Application` from the PowerShell tool), which is how phase 06 checked CSV row counts.
  - **Real-data shape (phase 06 probes, 2026-11-22):** 236,077 messages from 2026-02-27 to 2026-11-22; 66,884 tool_use rows (175 with a `tool_use_id`) and 92,938 `_tool_result` rows (319 with one; 1,929 errors, only 1 linked); 25,548 sidechain messages across 420 agent ids (all have an `agent_id`); 73 distinct git branches. The largest session, `bd0a5299…`, has 715 assistant turns, 1,329 sidechain records and 43 subagents.
  - **Phase 06 endpoint timings from this PC** (~150 ms per round-trip; much faster on the VPS): calendar 1.4 s, hourly 0.7 s, summary 4.3 s (all) / 1.7 s (30d; about 9 round-trips), the biggest session's insights 0.8 s, tools insights 1.7 s, search 0.6–1.3 s.
  - Old app on a copy of its DB, with nothing to rescan: `PORT=8080 python cli.py dashboard --no-scan --no-open --db <copy> --projects-dir <empty dir>`. Its 30-second scan loop always runs, even with `--no-scan`, so never point it at the real DB for a frozen comparison.

## Decisions & deviations

Record anything decided during implementation that isn't in README.md's Decisions table, with the date and the reason.

- **2026-11-22 (phase 06): new endpoints and their shapes** (all additive; pinned in `api/schemas_insights.py`, split from `schemas.py` to keep files small):
  - `GET /api/activity/calendar?metric=cost|tokens&days=365` (7–1100) → `{metric, timezone, start, end, days: [{day, value, cost_usd, tokens, sessions, turns}]}`. It lists **active days only**; the UI fills the grid. Cost is the `/api/daily` rollup (`daily_model_tokens` + `cost_by_model_per_key`).
  - `GET /api/activity/hourly` → all 168 `{dow (ISO 1–7), hour, turns, tokens, cost_usd}` cells.
  - `GET /api/activity/summary` → active days / days in range, current and longest streak, busiest day (by cost), per-active-day averages, total cost/tokens, top project (by turns) and peak hour (by turns). The **current streak** ends on the range's last day *or the day before* (an idle morning doesn't break it); with `until`, the last day is the local day before `until`.
  - **"Tokens" in phase 06 = core tokens** (input + output + cache writes). **"Turns" = `type='user'` records**, the overview's definition (tool results included); the hour grid's description says so.
  - `GET /api/sessions/{id}/insights` → the spec's fields, plus `uuid` per context point and `message_uuid` per tool event/invocation (for click-to-turn), `subagent_invocations` (the spec's "Task invocations"), `files_total` (files are capped at 100), `started`/`ended`, `cost_usd` and `tool_calls_linked`. An unknown id gives empty lists (200), like `sessions/{id}`.
  - `GET /api/tools/insights` → `{tools: [{tool_name, calls, linked, errors, error_rate, result_tokens}], calls, linked, linked_note, files, commands, domains}`. Result tokens and errors come from the `_tool_result` row joined by `tool_use_id`. **The old `/api/tools` `result_tokens` is always 0 for real tools** (the collector stores result tokens on `_tool_result` rows only); it is left as-is, and the Tools page uses the new endpoint. Commands include **PowerShell** beside Bash. Domains are lower-cased, without `www.`.
  - `GET /api/search?q=&limit=8` (1–20): snippets mark matches with **U+E000…U+E001** instead of `<b>` (no HTML to inject). Session hits are ordered by last activity; project hits match the derived display name or the slug.
  - `GET /api/export/{sessions,prompts,projects}.csv`: sessions/prompts take their list's filters **and sort**, paging internally by 200 (page 1 on the request connection, so a bad sort is a 422; later pages on a fresh pooled connection). Projects take the range plus an optional `q` (the Projects page's client-side name filter). UTF-8 with a BOM.
- **2026-11-22 (phase 06): CSV cells are made Excel-safe.** Text starting with `= + - @ \t \r` gets a leading `'` (CSV injection). Text longer than **32,000 Excel units** (UTF-16 code units, with each `"` counted twice because it's escaped) is cut with " …[truncated]". Why: a real 32,766-character prompt with 144 quotes still spilled into a second Excel row; Excel's import limit applies to the raw escaped field. `prompt_text` in the DB is untouched.
- **2026-11-22 (phase 06): the collector records `Agent` and `PowerShell` targets** (`_TARGET_FIELDS`: `Agent` → `subagent_type`, `PowerShell` → `command`). Claude Code renamed Task to Agent (219 calls, all with NULL target), and PowerShell (1,488 calls) is a shell on this PC. This only affects new ingests, or older rows after a `scan --full`.
- **2026-11-22 (phase 06): context growth is two charts, not a dual axis.** The spec said "output tokens on a secondary bar series"; the dataviz rules forbid two y-scales. The output bars sit in their own small chart on the same turn axis (hover is synced via `syncId`). Main-thread context is a line, sidechain turns are dots, and drops below half of a > 40k context are marked "compacted". **Zero-usage turns (`<synthetic>` records) are gaps**: on a real session they dove to 0 and produced two false "compacted" marks. The `<synthetic>` model is also hidden from the header chips.
- **2026-11-22 (phase 06): the calendar starts weeks on Monday** (ISO, to match the hour grid), not Sunday like GitHub. A day links to `/sessions?since=D&until=D` (inclusive, per the phase 05 note). The calendar always covers the last 365 days; the KPI cards and hour grid follow the range. Days are in the `timezone` setting, and the page says which.
- **2026-11-22 (phase 06): one sequential heat scale for both heatmaps**: the input blue mixed into `--card` at 0/28/52/76/100%, plus a new `--heat-0` token for "no activity". It's one hue with monotonic lightness by construction in both themes, quantised by quantiles of the non-zero values (so one huge day doesn't wash out the rest). The legend prints the numeric steps, and both heatmaps have a Table view.
- **2026-11-22 (phase 06): tool timeline = HTML lanes**, not Recharts: the busiest 7 tools plus "Other", ticks positioned by time, a fixed tool → colour map (Read / Edit / Write / shell, everything else grey), failures red and on top. One hover tooltip finds the nearest call within ~8px; a click jumps to its turn. Errors are only known for linked calls, and the card says how many.
- **2026-11-22 (phase 06): Cmd+K** needs ≥ 2 characters, debounced 200 ms. cmdk filtering is off (`shouldFilter={false}`; pages are filtered by title locally). A prompt opens `/sessions/<id>?turn=<uuid>`, and the session page jumps to that row once its records load.
- **2026-11-22 (phase 06): search performance fix.** A `LATERAL` per-title aggregate made a one-letter query time out (> 60 s; "commit" took 6.6 s). A join + `GROUP BY` brings both to ~0.3 s. Project names come from `SELECT DISTINCT project_slug, cwd` (~125 ms server-side, against 410 ms for `array_agg(DISTINCT …)`). No indexes were added.

- **2026-11-22 (phase 05): backend additions** (all additive; tests in `test_api.py` / `test_queries.py`):
  - `GET /api/daily` rows add `sessions`, `turns`, `cost_usd` and `cost_by_model` (`{model: usd}`; unpriced models left out). They're priced per (day, model) by `analytics.daily_model_tokens` + `costs.cost_by_model_per_key`, so the days sum to the overview cost.
  - `GET /api/overview`, `/api/daily` and `/api/by-model` take `project=<slug>` (an empty value means no filter). The project detail page is built from these.
  - `GET /api/projects/daily` → `[{project_slug, day, cost_usd}]` (days with no priced activity are absent). This is the spec's "`/api/projects/daily`" option.
  - `POST /api/tips/restore {key}` deletes the dismissal, for the Tips undo toast.
- **2026-11-22 (phase 05): TanStack Table v8, not v9.** v9 (the npm `latest`) renamed the core API (`createCoreRowModel`, `TableFeatures` generics). v8.21 is mature and React 19 compatible.
- **2026-11-22 (phase 05): dark mode has its own data-colour steps.** This changes phase 04's "data colours are the same in both themes": the hues are the same, the steps differ. The dataviz validator failed the light values on the dark lightness band. Darkening the blue alone collapsed it into the violet under deutan, so the blue sits high in the band and the violet low: `#4596f5 / #7350e8 / #c48628 / #36a07a` (mythos unchanged). Every check passes in both modes.
- **2026-11-22 (phase 05): `usePathname()` only inside `<Suspense>`.** On dynamic routes the pathname is URL data under Cache Components, and the build failed for `/projects/[slug]`. The top bar's title and range slot, and the sidebar's active state, now read it inside their own boundaries.
- **2026-11-22 (phase 05): Settings timezone.** The server stores `UTC` until set, and can't tell "unset" from "UTC". So Settings shows the stored zone plus a one-click "Use this browser's zone (…)" when they differ, instead of silently assuming the browser's zone. The page is mounted client-only, because it reads `Intl` while rendering.
- **2026-11-22 (phase 05): the session turn table defaults to "Turns"** (prompts + assistant turns; 313 of 702 rows on the checked session). "All records" shows the tool-result and attachment records too, as the old table always did. It's client-paginated at 100 rows and has a cost column.
- **2026-11-22 (phase 05): Tips undo** dismisses at once (optimistic) and calls `/api/tips/restore` on Undo. The alternative, a delayed dismissal, would be lost if the tab closed.
- **2026-11-22 (phase 05): old features intentionally changed** (everything else in `web/routes/*.js` is present):
  - Overview:
    - the **sunburst became a donut of families plus a full version list** (share bar, tokens, cost, raw ids on hover). The zoom interaction and the "smaller slices" line are gone; clicking a family filters the list instead;
    - the **five token KPI cards and the "Total tokens" card became the token composition bar** (tokens and cost per type, 5m/1h in the legend and tooltip, a Tokens/Cost share switch);
    - the **"Tokens by project" grouped input/output bar chart was dropped**: per-project input/output/cache reads are in the Top projects tooltip and in the Projects table;
    - the Projects and Turns KPIs became Prompts (turns) and the "N projects" sub-line on Sessions; Cache hit rate is new;
    - the glossary `<details>` became info tooltips, worded as before;
    - per-page range tabs became the global range picker (phase 04);
  - Prompts: the 200-row cap became server pagination. The "title" and "session" columns moved into the detail Sheet ("Open session"), and a project column was added. The "cache cost" column became the full turn cost (phase 03 fix). Sort adds Cost.
  - Sessions list: the session-id column became a clickable row (the id with a copy button is in the detail header). Project and model filters were added.
  - Session detail: the separate "Cache create (5m)/(1h)" cards are folded into the token composition. Duration is new; the turns filter is described above.
  - Projects list: the default sort is cost (was total tokens). A daily-cost sparkline, last active and a name filter were added; all the old columns are kept.
  - Skills: the page had its own range tabs defaulting to 30d; it now follows the global range (default All). A third KPI (SKILL.md tokens loaded) was added. Null tokens-per-call show "not scanned" with the KNOWN_LIMITATIONS hint.
  - Settings: the pricing note points at `backend/pricing.json` (auto-reloaded). Timezone, sync status, change password and a privacy-blur demo are new.
- **2026-11-22 (phase 05): browser checks ran on a throwaway copy of the data.** Creating a temporary login in the real `users` table was refused by the permission classifier. Instead, `claude_lens_test_e2e<hex>` was migrated and filled by a server-side `INSERT … SELECT` from `claude_dashboard` (data tables only, not `users`/`auth_sessions`), with a backend on :8001 bootstrapping its own admin from env. The schema was dropped afterwards. The real `users`, `auth_sessions` and `settings` were never written.

- **2026-11-22 (phase 04): no `dynamic = "force-dynamic"`.** With Cache Components the route segment config is gone. The API proxy and `/login/submit` call `await connection()` first instead, which has the same effect: they run per request and read `BACKEND_URL` at runtime. The build shows both as `ƒ`.
- **2026-11-22 (phase 04): `/login` sets `instant = false`** and awaits `searchParams` with no Suspense boundary, so it renders per request. Why: under Cache Components the page was otherwise a prerendered shell plus streamed content, and swapping in the streamed content needs JS. The no-JS fallback then lost `?next=` and the error message. The test caught this.
- **2026-11-22 (phase 04): the no-JS login posts to `/login/submit`**, a Next route handler that converts the form to JSON and answers with a 303 (the backend's CSRF guard rejects form encoding). It forwards the browser's `Origin`, so cross-site posts are still rejected. `next` goes through `safeNext()` (same-origin paths only).
- **2026-11-22 (phase 04): a 401 clears the cookie before redirecting.** `lib/api.ts` POSTs `/api/auth/logout` and then goes to `/login?next=…`. Without this, an expired cookie would loop: `proxy.ts` bounces `/login` (cookie present) back to the dashboard.
- **2026-11-22 (phase 04): the sidebar shortcut is Ctrl/Cmd+\\** (it was +B in shadcn), because Ctrl/Cmd+B is the privacy blur. The change is marked in `components/ui/sidebar.tsx`. `hooks/use-mobile.ts` was rewritten with `useSyncExternalStore` (shadcn's version fails the `react-hooks/set-state-in-effect` lint rule).
- **2026-11-22 (phase 04): the default range is `All`**, as in the old app. Presets are local calendar days: `7d` = today plus the previous 6 days, from local midnight. Custom ranges are `?since=YYYY-MM-DD&until=YYYY-MM-DD` (`until` inclusive), sent as `until` = the next local midnight (exclusive). Sidebar links carry the URL's range params, so a shared link keeps its range while you move between pages.
- **2026-11-22 (phase 04): the dashboard pages are static shells.** Data loads client-side with TanStack Query (staleTime 5 min, no refetch on focus, no retry on 4xx). Query keys are `[path, rangeKey, extraQuery]`, built in `lib/queries.ts`.
- **2026-11-22 (phase 04): Cmd+K lists the pages only for now** (the spec said "empty"). Phase 06 adds search. This shadcn version's `CommandDialog` does **not** add the `<Command>` root, so wrap the children in `<Command>` yourself.
- **2026-11-22 (phase 04): visual direction "instrument panel".**
  - Dark ink-navy surfaces (≈ the old `#0A0E14` palette) and a light paper theme.
  - The primary colour is the legacy blue; IBM Plex Sans for UI, JetBrains Mono (tabular) for numbers. The logo is the old blue→violet tile with the bars seen through a lens ring.
  - The data colours are the same in both themes.

- **2026-11-22 (phase 03): JSON shape changes beyond the pagination envelopes** (all additive or type-only):
  - `GET /api/sessions` and `GET /api/prompts` return `{items, total, page, page_size}`. Their params are `page`, `page_size` (≤ 200, default 50), `sort`, `order` (`asc`/`desc`; each sort has its own default), `q`, `project`, `model` and `since`/`until`. The old `limit` param is gone.
    - sessions `sort`: `ended` (default), `started`, `turns`, `tokens`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `total_tokens`, `cost`, `title`; `q` matches the title or session id;
    - prompts `sort`: `tokens` (default), `recent`, `cost`, `cache_read`, `chars`; `q` matches the prompt text. `sort=cost` is computed in SQL from `pricing.json` rates (the same formula as `cost_for`, NULLs last).
  - `sessions/{id}`: `is_sidechain` is a boolean (was 0/1), and `tool_calls_json` is **parsed JSON** (was a JSON string). An unknown session still returns `[]`.
  - prompts rows add the assistant turn's `input_tokens`, `output_tokens`, `cache_create_5m_tokens`, `cache_create_1h_tokens` and `cost_*_usd` breakdown. **`estimated_cost_usd` is now the full turn** (the fix).
  - `projects` rows add `last_active`. `projects/{slug}/sessions` also accepts `since`/`until`.
  - Timestamps serialise as ISO with `Z` (the API pool runs `SET TIME ZONE 'UTC'`); `daily.day` is `YYYY-MM-DD`.
- **2026-11-22 (phase 03): session cost follows the range.** In `/api/sessions` and `projects/{slug}/sessions`, `estimated_cost_usd` covers the same in-range messages as the token columns. The old app priced the whole session, even when `since` cut part of it off. With no range the values are identical.
- **2026-11-22 (phase 03): project names come from sorted cwds.** `project_names()` does one `array_agg(DISTINCT cwd)` query. When no cwd walks up to the slug, the fallback is the first cwd **in sorted order** (SQLite's order was arbitrary), so a project root now comes before its subfolders. On real data this changed 3 of 85 names, to the root folder (`Keyforge` instead of `UUID Generator`, `Zeeshan_Portfolio_v3` instead of `professional-profile-webpage`).
- **2026-11-22 (phase 03): new endpoints and their shapes.**
  - `GET /api/settings` → `{plan: string|null, timezone}`: `plan` is null until chosen, for phase 04's first-run picker. `GET /api/plan` still defaults to `"api"`.
  - `POST /api/settings` takes any subset of `{plan, timezone}`. The timezone is validated against `pg_timezone_names`, and plans against `pricing.json` → `plans` (422 otherwise; `POST /api/plan` validates too, where the old app accepted anything).
  - `GET /api/sync-status` → `{last_synced_at, machines: [{machine, last_run, last_ok_at}], runs: [last 20]}`.
  - `GET /api/health` → `{status, version}`.
- **2026-11-22 (phase 03): auth details.**
  - `POST /api/auth/logout` needs **no** login: it's idempotent and always 200.
  - A wrong `current` in `POST /api/auth/password` returns **400** (not 401, so the frontend doesn't bounce to the login page) and counts toward the lockout. The new password needs ≥ 8 characters (422), and so does `ADMIN_PASSWORD` at bootstrap.
  - Login responds `{username, expires_at}`, and so does `/auth/me`. The lockout 429 carries `Retry-After`. Success resets the counter. An unknown username still runs an argon2 verify (constant time).
  - The CSRF guard is ASGI middleware: 415 for a non-JSON `Content-Type`, 403 for a mismatched or `null` `Origin`. It applies to every non-GET request, **including login and logout**.
  - With `TRUST_PROXY=true` the client IP is the **last** `X-Forwarded-For` hop (the one our proxy appended). New env var `TRUST_PROXY` (default false) is in `Settings` and `.env.example`.
  - `claude-lens set-password <user>` **creates** the user if missing, and revokes all of that user's sessions.
- **2026-11-22 (phase 03): naive `since`/`until` mean UTC.** A value without an offset (e.g. `2026-11-01`) is UTC midnight. Phase 04 should send offset-qualified ISO strings (`Date.toISOString()`) built from the user's local day boundaries.
- **2026-11-22 (phase 03): the tips' dismissed check is one query** (`dismissed_keys`, `dismissed_at > now() - interval '14 days'`) instead of one query per tip.
- **2026-11-22 (phase 03): the test DB URL is redacted.** `pg_url` is a `str` subclass whose repr is `<DATABASE_URL redacted>`, because pytest printed the full URL (with password) in a fixture traceback. `pg_schema` now drops its schema over a **fresh** connection; the one held for the whole run had been closed by the server, which left schemas behind.

- **2026-11-22 (phase 00): `tool_use_id` is set on `_tool_result` rows too.** On those rows it's the block's `tool_use_id`, the same value already stored in `target`. Why: every tool dict now has identical keys, which keeps phase 01's COPY staging uniform. Phase 06 can also join a `tool_use` to its result with `u.tool_use_id = r.tool_use_id`. `target` is unchanged, so it still matches migrated SQLite rows.
- **2026-11-22 (phase 00): `format_for_user` was ported to `core/pricing.py`** along with `load_pricing`, `_tier_from_name` and `cost_for`. It's pure and has tests. Only `get_plan`/`set_plan` were left out.
- **2026-11-22 (phase 00): `DB_SCHEMA` is validated** as a plain SQL identifier (`^[A-Za-z_][A-Za-z0-9_]*$`) in `Settings`. Later phases should still quote it with `psycopg.sql.Identifier` when building `search_path`.
- **2026-11-22 (phase 00): `Settings` hides secrets in its repr.** `database_url` and `admin_password` are `repr=False`, so logging a `Settings` object doesn't leak them.
- **2026-11-22 (phase 01): transactions span files, not one per file.** Records from consecutive files are buffered until about 5,000 lines (`--batch-lines`), then written in one transaction together with every touched file's `files` offset. Big files are split across batches, each committing the offset it reached. Why: at 150 ms per round-trip, about 8 round-trips per transaction would make a 1,280-file scan take ~25 minutes. Walk order and "last wins" are unchanged.
- **2026-11-22 (phase 01): batch shape.** Messages and tool rows go through `COPY` into `TEMP … ON COMMIT DROP` tables (`s_messages` is `LIKE messages`). Titles and file offsets are inlined as `sql.Literal` VALUES in the single merge statement, which saves 4 round-trips per batch.
- **2026-11-22 (phase 01): dedup rule.** Keep the last occurrence per `uuid`, then the last per `(session_id, message_id)`, in walk/file order. Counts returned by `scan()` are records processed **before** dedup, exactly like `scan_dir`.
- **2026-11-22 (phase 01): accepted differences from SQLite.**
  - NUL characters are stripped, and unpaired surrogates become U+FFFD (Postgres text/jsonb reject both).
  - A record is **skipped** if its timestamp doesn't parse as ISO 8601, or its `type` or `uuid` is null, or `parse_record` raises (for example non-numeric usage). SQLite stored these or crashed the scan. Naive timestamps are read as UTC.
  - `prompt_tsv` indexes only the first 100,000 characters of `prompt_text`, because a tsvector over 1 MB makes the insert fail. `prompt_text` itself is stored in full.
  - `tool_calls.is_error` stays `INTEGER` 0/1 (the spec says "same columns"). Only `messages.is_sidechain` became `BOOLEAN`.
- **2026-11-22 (phase 01): retry semantics.** `scan` retries `psycopg.OperationalError` **3 times** after the first attempt (4 attempts in all), 60 seconds apart. Each attempt gets its own `sync_runs` row, and a failed attempt's row is closed as `error` ("connection lost: …") by the next one. `running` rows older than 6 hours on the same machine are closed as "interrupted". Any other exception closes the row as `error` with `Type: message`, with no retry.
- **2026-11-22 (phase 02): `migrate-sqlite` guard is stricter than the spec.** It refuses if **any** of `messages`, `tool_calls`, `session_titles`, `files` or `dismissed_tips` has rows, not just `messages`. Why: a stray `files` row would otherwise make the COPY fail on its primary key halfway through. `--force` truncates `messages, tool_calls, session_titles, files, settings, dismissed_tips` with `RESTART IDENTITY`; `sync_runs`, `skill_catalog`, `users` and `auth_sessions` are kept.
- **2026-11-22 (phase 02): migration extras.**
  - `--sqlite` defaults to `~/.claude/token-dashboard.db`;
  - `--check-only` re-runs the parity check without copying, and `--chunk` sets the chunk size;
  - all SQLite reads happen inside one read transaction, so the copy and the parity check see the same snapshot. The old DB is in `delete` (rollback-journal) mode, so the old scanner simply waits;
  - COPY writes straight into the real tables (they're empty, so no staging is needed). Text columns go through `ingest._clean_text`/`_clean_json` as a precaution, although the real data had no NULs or lone surrogates.
- **2026-11-22 (phase 02): parity covers more than the spec.**
  - Beyond the spec's list, it also checks `dismissed_tips`, `sum(result_tokens)`, the tool error count, exact `files (path, mtime, bytes_read)` equality and the plan. Per-model rows compare the row count plus all 5 sums.
  - On the Postgres side, `messages` and `files` are filtered by `machine`, while `tool_calls`, titles and tips are compared as totals. So `--check-only` only matches **right after** a migration; any later scan adds rows.
- **2026-11-22 (phase 02): logging lives in `cli.py`** (the `claude_lens.sync` logger), with no separate `daily.py`. Info goes to stdout and warnings/errors to stderr; each console handler is added only when its stream isn't None (pythonw). The rotating file handler is always added, unless the file can't be opened. Unexpected exceptions and config errors are logged with tracebacks. A new `Settings.sync_log` reads `CLAUDE_LENS_SYNC_LOG`, and a conftest autouse fixture points it at `tmp_path`, so tests never write to the real log.
- **2026-11-22 (phase 02): the installer warns** (it doesn't fail) when `.env.local` is missing, and fails when `backend\.venv\Scripts\pythonw.exe` is missing. The root README's "Daily background scan" section was rewritten for the new task. The user approved deleting `scripts/daily_scan.py`.
- **2026-11-22 (phase 01): test fixture shape.** There's one throwaway schema per pytest **session**, truncated before each test, instead of one schema per test, because each migrate+connect costs about 2 s over the network. DB tests are auto-marked `db`.

## Session log

Add newest entries at the top, using this template:

```
### YYYY-MM-DD: Phase NN, <done | partial | blocked>
- **Did:** …
- **Files:** created … / changed … / deleted …
- **Verification:** <commands run and their real results: test counts, row counts, parity numbers>
- **Commit:** <hash + message, or "uncommitted">
- **Gotchas:** …
- **Notes for the next session:** <concrete, actionable; these override the phase file where they conflict>
```

### 2026-11-22: Phase 06, done
- **Did:**
  - backend: `activity/{calendar,hourly,summary}`, `sessions/{id}/insights`, `tools/insights`, `search`, and `export/{sessions,prompts,projects}.csv`, plus tests. The sessions/prompts/projects routers now share their page builders with the export. The collector records `Agent` and `PowerShell` targets;
  - frontend: the Activity page (KPI cards, calendar heatmap, hour × weekday heatmap), the Tools page, the deep session view (chips, context growth + output, cost per turn, tool timeline, subagents, files touched, click-to-turn via `DataTable focusRow`), Cmd+K search, and the Export CSV buttons. `placeholders.tsx` is deleted;
  - probed the real data, fixed a search query that timed out, checked everything in headless Chrome and the CSVs in Excel; docs updated.
- **Files:**
  - backend created: `claude_lens/api/routers/{activity,tools,search,export}.py`, `claude_lens/api/schemas_insights.py`, `claude_lens/core/{activity,csv_export,session_insights}.py`, `claude_lens/db/queries/{activity,session_insights,tool_insights,search}.py`, `tests/test_feature_{units,api}.py`;
  - backend changed: `claude_lens/api/main.py`, `claude_lens/api/routers/{sessions,prompts,projects}.py`, `claude_lens/collector/parse.py`, `tests/{helpers,test_api,test_parse}.py`, `README.md`;
  - frontend created: `components/activity/{activity-page,calendar-heatmap,hour-heatmap,heat-legend}.tsx`, `components/charts/{heat-scale.ts,hover-tip.tsx}`, `components/sessions/{turn-charts,tool-timeline,insight-cards}.tsx`, `components/tools/tools-page.tsx`, `components/export-button.tsx`;
  - frontend changed: `app/(dashboard)/{activity,tools}/page.tsx`, `app/globals.css` (`--heat-0`), `components/data-table.tsx` (`focusRow`, `data-row-id`), `components/sessions/session-detail.tsx`, `components/shell/command-menu.tsx`, `components/{sessions,prompts,projects}/*-page.tsx` (export button), `lib/{queries,api-types}.ts`, `README.md`; deleted `components/placeholders.tsx`;
  - docs: this file, the phase 06 file (all boxes ticked, Outcome) and the phase 07 file ("from phase 06" notes).
- **Verification:**
  - Backend: `uv run pytest` (full suite) → **265 passed** in 690 s (240 + 25 new); afterwards `pg_namespace` held only `claude_dashboard`. The new files: `test_feature_units.py` 13 (offline), `test_feature_api.py` 11 (calendar across a UTC midnight under America/New_York, streaks, the hour grid, the insights shape, tools insights, search on a fixture prompt, a 205-row CSV over two pages, filters, formula guard, 401); `test_parse.py` +1. The environment check at session start gave 240 passed.
  - `pnpm typecheck`, `pnpm lint`: clean. `pnpm build`: `/activity` and `/tools` `○`, detail routes `◐`.
  - Old app: `python -m unittest discover tests` → **Ran 85 tests, OK**.
  - **Real data** (read-only probes, then a throwaway copy of `claude_dashboard` behind a backend on :8001 and `next start` on :3001): **headless Chrome 32/32 PASS**:
    - the calendar's earliest linked day is **2026-02-27** (210 active days, 365 squares); a day click → `/sessions?since=2026-11-22&until=2026-11-22` with 5 sessions; the Tokens toggle refetches; the tooltip shows cost/tokens/sessions; the hour grid has 168 cells;
    - session `bd0a5299…`: the context line (peak 431.1K; no false compaction marks after the `<synthetic>` fix), 43 subagent runs = $31.60 (54% of $58.44), 8 timeline lanes, "Top 15 of 161" files, branch + duration chips; the "most expensive" button and a click on the last cost bar both page the turn table (→ "Showing 701–781 of 781") and focus the row in view;
    - Tools: the coverage alert (0.3%), blurred commands and paths;
    - Cmd+K "ResuMatchAI" → 8 prompts with 25 highlights; keyboard Enter opens `/sessions/d67661d8…?turn=dd1a9529…`, scrolled to the turn; snippets blur under Ctrl+B;
    - the three Export CSV buttons download `claude-lens-<table>-2026-11-22.csv` with the page's filters, sort and range;
    - no horizontal overflow at 390px on Activity, Tools, the session, Sessions, Prompts or Projects; **no console errors or hydration warnings**; dark and light screenshots checked by eye.
  - **CSV vs API vs Excel** (opened through Excel COM): sessions **1,090 / 1,090 / 1,090**, prompts `q=commit` **69 / 69 / 69** (after the Excel-cap fix; before it, Excel showed 70), projects 30d **27 / – / 27**.
  - `pg_namespace` afterwards: only `claude_dashboard` (the e2e copy was dropped). The real schema was only read.
- **Commit:** `4540d78 feat: activity insights, deep session view, tools page, cmd+k search and csv export`, pushed to `mzeeshanaltaf/main`.
- **Gotchas:**
  - The React Compiler lint (`react-hooks/refs`) rejects reading fields off a hook's return object that also contains a ref (`tip.tip`, `tip.hide`). Destructure it.
  - The `<synthetic>` model: zero-usage assistant records (API errors, interruptions) appear inside real sessions. Exclude them from anything that reads "context size".
  - Excel's CSV cell limit counts the **escaped** field in UTF-16 units; `len()` isn't enough.
  - Playwright: `waitForURL("**/activity**")` also matches `/login?next=/activity`, so compare `pathname`. Recharts chart clicks need a preceding hover, and the chart must be scrolled into view first.
  - `next start` warns that it "does not work with output: standalone". It worked for local checks; production must use `node .next/standalone/server.js` (noted in phase 07).
  - The servers on :3000 and :8000 (from another session) were left alone; mine ran on :8001/:3001 and are stopped.
- **Notes for the next session:**
  - Ask the user about `claude-lens scan --full` (see Baton). After it runs, the Tools coverage alert should disappear and the subagent badges should show real types.
  - During the deploy, check a CSV export through the Coolify proxy (streaming), and Cmd+K over HTTPS.
  - Rebuild the throwaway e2e copy for browser checks as in phase 05's notes. This session's helper (`e2e_schema.py create|drop|list`) lived in the scratchpad.

### 2026-11-22: Phase 05, done
- **Did:**
  - backend: per-day sessions/turns/cost on `/api/daily`, a `project` filter on overview/daily/by-model, `/api/projects/daily`, `/api/tips/restore`, plus tests;
  - frontend: the Overview, Prompts (+ detail Sheet), Sessions (+ `/sessions/[id]`), Projects (+ `/projects/[slug]`), Skills, Tips and Settings pages, and the shared table/chart/filter layer they use;
  - validated the chart palette with the dataviz script and added dark-mode steps;
  - fixed the shell's `usePathname` reads for dynamic routes;
  - trimmed `placeholders.tsx` to Activity and Tools;
  - wrote `frontend/README.md` § Page patterns, added the endpoints to `backend/README.md`, and added notes to the phase 06 file.
- **Files:**
  - backend changed: `claude_lens/api/routers/{analytics,projects,tips}.py`, `claude_lens/api/schemas.py`, `claude_lens/core/{costs,tips}.py`, `claude_lens/db/queries/analytics.py`, `tests/test_{api,queries}.py`, `README.md`;
  - frontend created:
    - `app/(dashboard)/{sessions/[id],projects/[slug]}/page.tsx`;
    - `components/{bar-list,data-table,detail-header,filters,info-tip,model-badge,section-card,sparkline,turn-breakdown}.tsx`;
    - `components/charts/{token-composition,daily-chart,model-mix}.tsx`;
    - `components/{overview,prompts,sessions,projects,skills,tips,settings}/*`;
    - `hooks/{use-url-state,use-server-table}.ts`, `lib/{glossary,usage}.ts`;
  - frontend changed: the 7 route `page.tsx` files, `app/globals.css` (dark data steps), `components/placeholders.tsx`, `components/shell/{app-sidebar,top-bar}.tsx`, `components/ui/chart.tsx` (a `valueFormatter` prop, marked `Claude Lens:`), `lib/{api-types,format,queries}.ts`, `package.json` / `pnpm-lock.yaml` (`@tanstack/react-table` 8.21.3), `README.md`;
  - docs: this file, the phase 05 file (all boxes ticked, Outcome) and the phase 06 file ("Notes from phase 05").
- **Verification:**
  - `pnpm typecheck`, `pnpm lint`: clean (0 warnings). `pnpm build`: 7 core routes `○`, `/sessions/[id]` and `/projects/[slug]` `◐`.
  - Backend: `uv run pytest tests/test_api.py tests/test_queries.py` → 54 passed; `test_api.py tests/test_tips.py` → 32 passed after the tips/daily additions. Full suite `uv run pytest`: **240 passed** in 731 s (235 + 5 new: daily cost, project filter, projects/daily, daily_model_tokens, cost_by_model_per_key; the tips undo and OpenAPI path checks extend existing tests). Afterwards `pg_namespace` held only `claude_dashboard`.
  - Old app: `python -m unittest discover tests` → **Ran 85 tests, OK**.
  - **Old vs new** (old app on a scratchpad copy of its SQLite with an empty projects dir, so no rescans; new API on the e2e copy of `claude_dashboard`):
    - with no cutoff, the old app was slightly ahead (its last scan, in phase 03, ran a few minutes after the last Postgres sync: turns 98,953 vs 98,948, cost $6,438.9984 vs $6,438.7082, same 1,090 sessions / 85 projects);
    - **at `until=2026-11-22T11:55:00Z` (before the last sync) all 15 overview fields are identical**: sessions 1,090, projects 85, turns 98,937, input 2,361,204, output 64,229,362, cache_read 11,280,484,719, cache_5m 29,362,694, cache_1h 197,657,259, cost $6,437.9321 (input 10.8757, output 1,229.7341, cache_read 3,535.2405, 5m 122.8509, 1h 1,539.2309, create 1,662.0818);
    - **all 85 project rows identical** on sessions/turns/tokens/cost. Spot check Flourish Backend API: 225 sessions, 19,238 turns, total 2,387,789,110 tokens, $1,597.1404 on both;
    - session `011f0861…`: 702 records on both, cost $74.0637, output 243,710, cache_read 93,118,763 on both.
  - **The UI shows the API's numbers:** Overview (range All) $6,438.71 / 1,090 / 98,948, the plan note "You pay $20/mo on Pro"; project page $1,597.14; session page $74.06 with 702 records.
  - **Headless Chrome, 25/25 PASS** (`playwright-core` + system Chrome against `next start` on :3001):
    - the daily Cost mode legend and table view; the model-mix family filter;
    - Ctrl+B gives `blur(6px)`; a Top-project click keeps `?range=90d`;
    - the prompt Sheet (full prompt + breakdown); `sort=recent` in the URL; search "commit" narrows 493 → 69;
    - the sessions Cost header gives `sort=cost&order=desc` with a top row of $74.06; next page gives `page=2`;
    - Turns/All records 313 → 702; the turn dialog shows tool calls;
    - tip dismiss is optimistic (3 → 2, API 2), Undo restores it (3, API 3);
    - the timezone saves from the browser (Asia/Karachi); a wrong current password shows a message with no logout; a password change signs out to /login, and the new password works.
  - **Console: no hydration warnings or errors** on any page at 1440px or 390px. The only console line is the deliberate wrong-password 400. **No horizontal page overflow at 390px** on any of the 9 pages (wide tables scroll inside their cards). Screenshots in dark and light (Overview) were checked by eye.
- **Commit:** `06718a3 feat(frontend): redesigned core pages with daily cost, project filters and tips undo`, pushed to `mzeeshanaltaf/main`.
- **Gotchas:**
  - The `react-hooks/incompatible-library` lint warning on `useReactTable` is suppressed. That's fine **only while the React Compiler is off** (it is; `next.config.ts`). If it's ever enabled, add `"use no memo"` to `DataTable`, or rows go stale.
  - TanStack only sorts columns that have an accessor. `DataTable` adds a no-op accessor to server-sorted display columns. Without it, the headers silently weren't sortable.
  - Playwright's `waitForLoadState("networkidle")` returns at once once the page has reached it, so wait for the specific response (`page.waitForResponse`) after a click. Slow queries (ILIKE search, sort by cost) take 1–3 s over the network from this PC.
  - The Recharts 3 legend sorts items alphabetically by default; pass `itemSorter={null}`.
  - shadcn's `CardHeader` has its own grid template; overriding `grid-cols-*` on it scrambles the layout (the first Tips cards did this). Use `CardContent` + flex for custom header rows.
  - Two other servers were running from a different Claude Code session (:3000 dev, :8000 backend without reload, started 16:37). They were left alone; mine ran on :8001/:3001/:8080 and are stopped.
- **Notes for the next session:**
  - Reuse `DataTable`, `useServerTable`, `FilterBar`/`SearchBox`/`ProjectSelect`, `SectionCard`, `BarList`, `KpiCard` and `InfoTip`. For new per-day series, extend `/api/daily` or reuse `daily_model_tokens` + `cost_by_model_per_key`.
  - The Activity calendar's day link must use an **inclusive** `until` (`?since=D&until=D`); see the phase 06 notes.
  - The deep session view can hang its new charts above the turn table in `components/sessions/session-detail.tsx`. Mind the 100-row pagination and the Turns/All filter when scrolling to a turn.
  - For browser checks without the admin password, use the throwaway-schema copy approach (see Decisions). The helper used here lived in the session scratchpad and is gone. Recreate it: `Settings.from_env({..., "DB_SCHEMA": "claude_lens_test_e2e<hex>"})`, `migrate(conn, schema)`, then `INSERT INTO <schema>.<t> (<cols>) OVERRIDING SYSTEM VALUE SELECT <cols> FROM claude_dashboard.<t>` for messages, tool_calls, files, session_titles, settings, dismissed_tips, skill_catalog and sync_runs (columns from `information_schema` with `is_generated = 'NEVER'`, which skips `prompt_tsv`). Start the backend with that `DB_SCHEMA` plus `ADMIN_USERNAME`/`ADMIN_PASSWORD`, and `DROP SCHEMA … CASCADE` at the end.

### 2026-11-22: Phase 04, done
- **Did:**
  - scaffolded `frontend/` (create-next-app 16.4.6, then `shadcn init --base radix --preset nova`) and added the 23 components from the spec, plus field, spinner, empty and alert;
  - set the design tokens (`--chart-input/-output/-cache-write/-cache-read`, `--family-*`, success/warning);
  - built the API proxy, `proxy.ts`, the typed API client from OpenAPI, the TanStack provider, the login page with its no-JS fallback, the full app shell, the formatting/model/chart-colour helpers, the shared UI pieces, and placeholders for all 9 routes;
  - set `output: "standalone"`, `/` → `/overview` (a next.config redirect), and an SVG favicon;
  - wrote `frontend/README.md`.
- **Files:**
  - created: everything under `frontend/`. The hand-written parts:
    - `app/{layout.tsx,globals.css,icon.svg}`, `app/api/[...path]/route.ts`, `app/login/{page.tsx,submit/route.ts}`, `app/(dashboard)/{layout.tsx,<9 routes>/page.tsx}`, `proxy.ts`, `next.config.ts`;
    - `components/{providers,logo,login-form,kpi-card,empty-state,error-state,loading,placeholders}.tsx`, `components/shell/{app-sidebar,top-bar,range-picker,sync-badge,privacy,kbd,command-menu,user-menu,plan-picker,client-only}.tsx`;
    - `hooks/use-range.ts`, `lib/{api,api-types,backend,queries,range,format,models,chart-colors,nav,safe-next,login-messages}.ts`;
    - edited shadcn files: `components/ui/sidebar.tsx` (shortcut) and `hooks/use-mobile.ts`;
  - changed: this file and the phase 04 file.
- **Verification:**
  - `pnpm typecheck`, `pnpm lint`: clean. `pnpm build`: all 9 dashboard routes static (`○`); `/login`, `/login/submit` and `/api/[...path]` dynamic (`ƒ`); proxy present.
  - **curl through :3000** (backend with `COOKIE_SECURE=false TRUST_PROXY=true`):
    - signed-out `/overview` → 307 `/login?next=%2Foverview`; signed-out `/api/overview` → 401;
    - wrong password → 401; `Origin: http://evil.example` → 403;
    - login → 200 with `set-cookie: cl_session=…; HttpOnly; Max-Age=604800; Path=/; SameSite=lax`. Then `/api/overview` → 200 with **sessions 1,090, projects 85, turns 98,948** (equal to phase 03's totals check), `/login` with the cookie → 307 `/`, and `/overview` → 200;
    - logout → 200, `Max-Age=0`, then 401;
    - no-JS: a bad password → 303 `/login?error=invalid&next=…`; good → 303 to `next`; `next=//evil.example/x` → `/overview`; a cross-site form post → 303 `?error=server` (the backend's 403);
    - lockout: 5×401, then 429, and the form path → `?error=locked&retry=897`, rendered as "Try again in 14 minutes".
  - **Headless Chrome** (`playwright-core` + system Chrome, scratchpad script) against `pnpm dev`: **26/26 PASS**:
    - signed out → login; the wrong-password message; sign in → `/overview`, showing **$6,438.71** (all time);
    - clicking 7d → URL `range=7d`, refetch `/api/overview?since=2026-11-15T19:00:00.000Z`, now **$138.96**; localStorage `lens.range=7d`; reloading `/overview` with no param keeps 7d;
    - a custom `since`/`until` in the URL is sent as both params; sidebar links carry `?range=30d`;
    - Ctrl+B: `filter: blur(6px)` and back to `none`, and the sidebar stays expanded; Ctrl+K opens the palette and navigates to `/tools`;
    - every placeholder shows a number; the light theme toggles; logout → `/login` with no `cl_session` cookie, then `/overview` → login;
    - **console: no hydration warnings.** The only console error is the expected 401 from the wrong-password attempt;
    - no-JS context: the error message renders, and sign-in lands on `/sessions?range=7d`.
  - Screenshots of login, overview (dark and light) and the blurred prompts page were checked by eye.
- **Login used for the checks:** a temporary user `lens-e2e` with a random password, created in the real `users` table through `claude_lens` helpers, because the admin password isn't available to the session. It was **deleted afterwards**, together with its 3 sessions; `users` again holds only `admin`. 6 failed attempts for the nonexistent `nobody-e2e` sit in the in-memory lockout until the backend restarts (harmless).
- **Commit:** `b44dd0a feat(frontend): next.js shell, login, api proxy and date-range plumbing`, pushed to `mzeeshanaltaf/main`.
- **Gotchas:**
  - The shadcn CLI writes `import { cn } from "cn"`. That's the real `cn` package, not a broken alias (I briefly "fixed" it and then reverted).
  - Cache Components: any client component that calls `useSearchParams` (`useRange`, `useRangedQuery`, the sidebar's range links) needs a `<Suspense>` above it. The dashboard layout wraps `children`, and the top bar wraps the range picker.
  - shadcn's `CommandDialog` needs an explicit `<Command>` child (see Decisions).
  - `curl --data-urlencode name@file` keeps the file's trailing newline in the value. Trim it before you blame the code.
  - A `pnpm build` while `pnpm dev` is running didn't disturb the dev server.
  - The Next dev-tools "N" badge covers the bottom-left of the sidebar in dev only.
- **Notes for the next session:**
  - Replace `components/placeholders.tsx` one page at a time. Keep `KpiCard`, `EmptyState`, `ErrorState` and the skeletons, or extend them. Charts: spread `tokenChartConfig` / `familyChartConfig` into the `ChartConfig` and use `var(--color-<key>)` inside the ChartContainer. Load the `dataviz` skill first, as phase 05 says.
  - **The Overview's "Est. cost" sparkline needs daily cost**, but `/api/daily` only returns tokens (`day`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_create_tokens`). Add `cost_usd` per day in the backend (a phase 05 addition; `core/costs.py` already has the per-model rollup), then run `pnpm gen:api`.
  - After any backend schema change, run `pnpm gen:api` with the backend running and commit `lib/api-types.ts`.
  - Settings' change-password form goes at `/settings#password` (the user menu links there). On success the backend revokes all of the user's sessions, so expect a 401 → login afterwards (see phase 03's notes on 400 vs 401).
  - Mark sensitive text with `blur-sensitive`. For page-level data, use `useRangedQuery(path, extraQuery)`; for paginated tables, put `page`/`sort` in `extraQuery` so they're part of the key.
  - To check the first-run dialog live: temporarily `DELETE FROM claude_dashboard.settings WHERE k = 'plan'`, or exercise it in a test schema. Restore `"pro"` afterwards (the dialog's Continue does it, or `POST /api/settings {"plan":"pro"}`).

### 2026-11-22: Phase 03, done
- **Did:**
  - ported every `db.py` query to `db/queries/*.py` (named `%(x)s` params, `COUNT(*) FILTER`, `::bigint` sums, `AT TIME ZONE` day buckets). The N+1 cwd lookups became one `array_agg(DISTINCT cwd)` query;
  - server-side pagination, sort whitelists and filters for sessions and prompts; `sort=cost` runs in SQL via a `jsonb_to_recordset` rates CTE;
  - `core/costs.py` (the `_cost_by_key` / `_cost_breakdown_by_key` / overview rollup, plus per-turn cost) and `core/tips.py` (4 rule sets on Postgres);
  - **the prompt cost fix** (full assistant turn);
  - plan and timezone settings, and `sync-status`;
  - the FastAPI app: lifespan with pool + migrate + admin bootstrap, routers under `/api`, Pydantic response models;
  - auth: argon2 via pwdlib, sha256-only tokens, the sliding cookie, lockout and CSRF middleware;
  - `claude-lens set-password`, and the pricing mtime loader.
- **Files:**
  - created: `backend/claude_lens/api/{__init__,main,auth,deps,schemas,security}.py`, `backend/claude_lens/api/routers/{__init__,analytics,projects,sessions,prompts,tips,settings}.py`, `backend/claude_lens/core/{costs,tips,passwords}.py`, `backend/claude_lens/db/queries/{__init__,common,analytics,projects,sessions,prompts,settings,sync,auth}.py`, `backend/tests/test_{queries,tips,end_to_end_totals,api,auth,api_units}.py`;
  - changed: `backend/claude_lens/{cli,config}.py`, `backend/claude_lens/core/pricing.py` (`make_pricing_loader`), `backend/claude_lens/db/pool.py` (UTC sessions), `backend/tests/{conftest,helpers,test_cli}.py`, `backend/README.md` (§ API), `.env.example` (`TRUST_PROXY`), this file, and the phase 03 and 04 files.
- **Verification:**
  - `cd backend && uv run pytest`: **235 passed, 1 error** in 592 s. The error was the session teardown's `DROP SCHEMA` on a server-closed idle connection, not a test. Fixed in `conftest.py`. **Full rerun: 235 passed, 0 errors in 585 s**, and no `claude_lens_test_%` schemas were left behind. `-m "not db"`: **105 passed** in 0.6 s; 130 DB tests. New files: queries 31, tips 11, end-to-end 1, api 21, auth 18, api_units 15; cli +2.
  - `python -m unittest discover tests` (old app): **Ran 85 tests, OK**.
  - **Live exit check** (real schema, `uvicorn … --port 8000`, after `claude-lens scan`):
    - `curl -i /api/overview` → **401**; `curl -c jar` login → 200 `{"username":"admin",…}`; `curl -b jar /api/overview` → **200**;
    - logout → `{"ok":true}`, then 401 with the old cookie;
    - `/docs` → 200, with **20 paths** in `openapi.json`.
  - **Totals vs the old app** (`python cli.py dashboard` on 8080, `range=all`, both freshly scanned): **all 15 fields identical**. cost_usd **6438.7082** = 6438.7082; sessions 1,090; projects 85; turns 98,948; input 2,361,224; output 64,235,228; cache_read 11,283,008,440; cache_5m 29,362,694; cache_1h 197,676,508; cache-create cost 1662.2358.
  - **Other endpoints, old vs new:** by-model (14), daily (210), tools (48), skills (55 rows, `tokens_per_call` equal), tips (3), plan + pricing, one session's 2,557 turns, and 200 sessions/prompts rows are all identical. The exceptions: this live session (scanned a few seconds apart), prompts' `estimated_cost_usd` (the fix), and `project_name` for 3 projects / 33 sessions (sorted-cwd fallback, see Decisions).
- **Admin seeding (local):** the first API start set `ADMIN_USERNAME=admin` and `ADMIN_PASSWORD` as process env vars only (`.env.local` was not changed). The generated password was given to the user privately (it was kept in the session scratchpad); they should replace it with `uv run claude-lens set-password admin`. The real `users` table holds `admin`; `auth_sessions` is empty.
- **Commit:** `7b47238 feat(api): fastapi endpoints, pagination and single-admin auth on postgres`, pushed to `mzeeshanaltaf/main`.
- **Gotchas:**
  - **pytest prints fixture values in tracebacks**: a teardown error dumped the full `DATABASE_URL` into the test output. Fixed by redacting `pg_url`'s repr. Never paste raw pytest failure output into docs.
  - Two stray test schemas (`claude_lens_test_74e57b2c`, `…_6d95f6f5`) were found and dropped. Only `claude_dashboard` remains.
  - psycopg sends Python `str` as an *unknown*-typed parameter, so ISO strings insert fine into `timestamptz` (handy in tests). Without params, `%` in SQL is literal; with params it must be `%%`. The queries avoid `LIKE` literals (they use `strpos`) to sidestep this.
  - FastAPI yield dependencies: endpoints that write call `conn.commit()` themselves before returning, so the change is durable before the response is sent.
  - Git Bash rewrites `/docs` inside a `curl -w` format string into a Windows path; it's cosmetic.
- **Notes for the next session:**
  - Generate TS types from `http://localhost:8000/openapi.json`. Paginated responses are `SessionPage` / `PromptPage`.
  - The proxy must forward `content-type`, `origin`, `x-forwarded-host` and `x-forwarded-for`, and cookies both ways. Logout must POST JSON (`{}`). See the note added to the phase 04 file.
  - First-run plan picker: show it when `GET /api/settings` returns `plan: null`. Save with `POST /api/settings {plan}`.
  - Synced badge: `GET /api/sync-status` → `last_synced_at` plus `machines[].last_run.status` (`ok`/`error`/`running`) and `.machine`.
  - Send `since`/`until` with explicit offsets. `/api/daily` buckets by the `timezone` setting (default UTC); phase 05's Settings can set it.
  - A 401 means "not logged in". A wrong current password on change-password is 400; lockout is 429 with `Retry-After`.

### 2026-11-22: Phase 02, done
- **Did:**
  - wrote `collector/migrate_sqlite.py` and the `claude-lens migrate-sqlite` command: read-only SQLite, one snapshot, chunked COPY, commit per table, ANALYZE, and a built-in parity table;
  - ran the migration and the first incremental scan against the real `claude_dashboard` schema;
  - added rotating-file logging to the `scan` path;
  - rewrote `scripts/install_daily_scan.ps1` for `Claude Lens - Daily Sync`, which also removes the old task;
  - deleted `scripts/daily_scan.py` (the user approved);
  - installed the task and triggered it.
- **Files:**
  - created: `backend/claude_lens/collector/migrate_sqlite.py`, `backend/tests/test_migrate_sqlite.py`;
  - changed: `backend/claude_lens/cli.py` (`migrate-sqlite`, the sync log), `backend/claude_lens/config.py` (`sync_log` / `default_sync_log`, `CLAUDE_LENS_SYNC_LOG`), `backend/tests/{conftest,test_cli}.py`, `backend/README.md`, `README.md` (daily sync section), `.env.example`, `scripts/install_daily_scan.ps1`, this file and the phase 02 file;
  - deleted: `scripts/daily_scan.py`.
- **Verification:**
  - `cd backend && uv run pytest`: **144 passed, 1 error** in 320 s. The error was a transient `OperationalError` in the `db` fixture setup for `test_skills_upload.py::test_upload_defaults_to_scanning_disk`; a rerun of that file gave 3 passed. That makes 145 tests, all green. The new files: `test_migrate_sqlite.py` 13, `test_cli.py` +5.
  - `python -m unittest discover tests` (old app): **Ran 85 tests, OK**.
  - **Migration** (`uv run claude-lens migrate-sqlite`, 54.5 s): 235,402 messages (28.9 s), 159,328 tool_calls (10.6 s), 1,280 files, 1,002 session_titles, 7 dismissed_tips, plan `pro`. **Parity ok: 30 checks match.** The checks:
    - row counts, and 1,085 distinct sessions;
    - token sums: input 2,360,848, output 63,882,836, cache_read 11,257,043,507, cache_5m 29,362,694, cache_1h 196,911,825;
    - result_tokens 45,489,804, 1,928 tool errors;
    - 15 per-model rows (including `(none)` and `<synthetic>`);
    - exact `files` offsets, and the plan.

    These are the same as the 2026-11-20 planning numbers; the old scanner hadn't run since.
  - **First scan afterwards** (manual, 7.4 s): `scanned 7 files: 684 messages, 407 tool calls, 75 titles in 1 batches; 570 skills in catalog`. That's 7 of the 1,284 files on record.
  - **Scheduled task:** `Start-ScheduledTask` gave LastTaskResult **0**. The log shows `scanned 1 files: 13 messages, 6 tool calls, 1 titles …`, and `claude-lens status` lists it as `#2 … ok 4.2s Zeeshan-Desktop files=1 messages=13`. Next run: 2026-11-23 13:00.
  - `Get-ScheduledTask` for `Claude*` lists **only** `Claude Lens - Daily Sync`.
  - Row counts after the task: messages 235,835, tool_calls 159,637, session_titles 1,006, files 1,284, sessions 1,089, sync_runs 2.
  - The SQLite sha256, mtime and size are unchanged.
- **Commit:** `2947df1 feat(collector): sqlite history migration with parity check and daily sync task`, pushed to `mzeeshanaltaf/main`.
- **Gotchas:**
  - A pythonw path with spaces (`E:\Projects\Claude Code\…`) works fine as the task's `-Execute` without extra quoting.
  - The DB test suite is network-bound (≈5 min) and can hit a transient `OperationalError` in fixture setup. Rerun the file before you suspect the code.
  - `scan` counts are records processed before dedup, so the two post-migration scans' 684 + 13 "messages" added only 433 message rows net (235,402 → 235,835). The rest were streaming snapshots that dedup collapsed.
- **Notes for the next session:**
  - The real schema now has real data. Phase 03's API tests must still use the throwaway-schema fixtures. For a manual sanity check, use `claude-lens status` on the real schema; its counts are above.
  - `settings` rows are jsonb: `plan` is the JSON string `"pro"`. `GET/POST plan` should read and write `v` as a JSON string.
  - `dismissed_tips.dismissed_at` is `timestamptz` (converted from epoch).
  - `tool_calls.tool_use_id` is NULL for the 159,328 migrated rows. Phase 06 already accounts for this.

### 2026-11-22: Phase 01, done
- **Did:**
  - wrote the Postgres schema (`001_init.sql`) and an advisory-locked migration runner;
  - wrote the `search_path` connection helpers and pool factory;
  - wrote the batched collector, keeping the SQLite scanner's skip/offset/partial-line/dedup semantics, plus the skill catalog upload;
  - implemented `claude-lens scan` (with retries and `sync_runs`) and `claude-lens status`;
  - added the throwaway-schema pytest fixtures and ported the dedup, rescan, walk and titles tests, plus robustness, unit, migration, catalog and CLI tests.
- **Files:**
  - created: `backend/claude_lens/db/{__init__,pool,migrate}.py`, `backend/claude_lens/db/migrations/001_init.sql`, `backend/claude_lens/collector/ingest.py`, `backend/tests/helpers.py`, `backend/tests/test_ingest_{dedup,rescan,walk,titles,robustness,unit}.py`, `backend/tests/test_{migrate,skills_upload}.py`;
  - changed: `backend/claude_lens/cli.py`, `backend/claude_lens/collector/skills_catalog.py` (`upload_catalog`), `backend/tests/{conftest,test_cli}.py`, `backend/pyproject.toml` (the `db` marker), `backend/README.md`, `.env.example` (`TEST_DATABASE_URL`), this file and the phase 01 file.
- **Verification:**
  - `cd backend && uv run pytest`: **129 passed** in 170 s. `-m db`: 43 passed. `-m "not db"`: 86 passed in 0.15 s.
  - `python -m unittest discover tests` (old app): **Ran 85 tests, OK**.
  - **Exit check 1:** copied `e--Projects-Claude-Code-1-Applications-ResuMatchAI` (81 MB, 19 JSONL files, 10,715 lines) to the scratchpad and ran `DB_SCHEMA=claude_lens_test_exit… claude-lens scan --projects-dir <copy>` twice.
    - Run 1: `scanned 19 files: 5933 messages, 3760 tool calls, 681 titles in 3 batches; 570 skills in catalog`, 11.3 s wall clock (7.4 s between the `sync_runs` timestamps).
    - Run 2: `scanned 0 files … in 0 batches`, 5.1 s wall clock (2.2 s run). It's mostly connect, migrate check and catalog upload.
  - **Parity:** ran the old `token_dashboard.scanner.scan_dir` on the same copy into a temp SQLite DB. Identical results:
    - scan_dir's own totals: 5,933 / 3,760 / 681 / 19;
    - rows: 3,724 messages, 3,020 tool_calls, 17 titles, 19 files, 17 sessions;
    - all 5 token sums, per-model sums (7 models), tool result tokens and errors, and prompt chars;
    - the uuid sets are identical.
  - **Exit check 2:** appended a copy of a real assistant line (new uuid, same `message.id`, `output_tokens` 999,999) and re-scanned. That scanned 1 file and 1 message. Exactly one row is left for `msg_011Cgv…`, and it's the new snapshot.
  - The exit-check schema was dropped afterwards. `pg_namespace` has no `claude%` schemas left, and `claude_dashboard` was never created.
- **Commit:** `3530e74 feat(collector): postgres schema, migrations and batched ingest`, pushed to `mzeeshanaltaf/main`.
- **Gotchas:**
  - **Postgres collation isn't byte order.** `ORDER BY model` sorts differently from SQLite, which broke a naive list comparison in the parity check. Phase 02's parity check and phase 03's ported query tests should compare as dicts/sets, or use `COLLATE "C"` where byte order matters.
  - `sum(bigint)` returns `numeric`, which psycopg gives back as `Decimal`. Cast (`::bigint`) or `int()` it before comparing or JSON-encoding.
  - The skill catalog registers an `<ancestor>:<skill>` slug for **every** ancestor folder, so a skill under a temp path yields about 9 slugs. Tests assert membership, not counts.
  - `load_settings()` writes `.env.local` values into `os.environ`. An autouse fixture in `conftest.py` restores the environment after each test. Any CLI test that connects **must** set `DB_SCHEMA` to the test schema first, or `.env.local`'s schema would be used.
  - Each `claude-lens scan` costs about 30 round-trips (≈5 s) even with nothing to do.
- **Notes for the next session:**
  - Use `claude_lens.db.pool.connect(settings)` for one-off connections. It sets `search_path`. Call `migrate(conn, settings.db_schema)` on an **idle** connection before writing.
  - The `files` table is `(machine, path, mtime DOUBLE PRECISION, bytes_read BIGINT, scanned_at TIMESTAMPTZ)`. Copy `path`, `mtime` and `bytes_read` from SQLite verbatim, with `machine = settings.machine` (`Zeeshan-Desktop`), so the first real `scan` skips the 1,202 unchanged files.
  - `messages` has a generated `prompt_tsv`: exclude it from the COPY column list. `tool_calls.is_error` is `INTEGER`, so copy 0/1 as-is. `messages.is_sidechain` is `BOOLEAN` (Postgres also accepts the text `'0'`/`'1'`). `tool_calls_json` is jsonb: SQLite text that contains `\u0000` or unpaired surrogate escapes will fail, so reuse `ingest._clean_json` / `_clean_text` for the migrated text columns.
  - `migrate-sqlite` should TRUNCATE `messages, tool_calls, session_titles, files, settings, dismissed_tips` for `--force` (not `sync_runs`, `skill_catalog` or `users`).
  - For the daily task: the CLI already prints `scanned N files: …` on success, which phase 02's log check looks for. `print()` is a no-op under `pythonw` (where `sys.stdout` is None), so add the file log handler as the phase file says.

### 2026-11-22: Phase 00, done
- **Did:**
  - fixed `.gitignore` (`.env*`, `!.env.example`, `.next/`, `backend/.venv/`, `.pytest_cache/`, `*.egg-info/`) and added `.env.example` (names only);
  - created the `backend/` uv project and `config.py` (`Settings` + a stdlib `.env.local`/`.env` loader);
  - copied the pure modules into `claude_lens/` (`core/pricing.py`, `core/names.py`, `collector/parse.py` with `tool_use_id`, `collector/skills_catalog.py`) and `pricing.json` into `backend/`;
  - ported the tests to pytest and added a stub CLI.
- **Files:**
  - created: `.env.example`, `backend/{pyproject.toml,uv.lock,README.md,pricing.json}`, `backend/claude_lens/{__init__,config,cli}.py`, `backend/claude_lens/core/{__init__,pricing,names}.py`, `backend/claude_lens/collector/{__init__,parse,skills_catalog}.py`, `backend/tests/{conftest,test_pricing,test_names,test_parse,test_skills_catalog,test_config,test_cli}.py`, `backend/tests/fixtures/*` (copied);
  - changed: `.gitignore`, this file, and the phase 00 file (boxes ticked, Outcome line).
- **Verification:**
  - `cd backend && uv run pytest`: **71 passed** in 0.10s (cli 6, config 14, names 11, parse 13, pricing 17, skills_catalog 10);
  - `uv run claude-lens --help` lists scan, migrate-sqlite, status and set-password;
  - `python -m unittest discover tests`: **Ran 85 tests, OK**;
  - `git check-ignore -v .env.local` matches `.gitignore:13:.env*`, and `git status` doesn't list `.env.local` (`.env.example` stays visible).
- **Commit:** `feat(backend): claude-lens uv scaffold with ported pure modules`, pushed to `mzeeshanaltaf/main` (find the hash with `git log --oneline -1`). It also includes the planning docs, the CLAUDE.md pointer, `.gitignore` and `.env.example`.
- **Gotchas:**
  - `python3` is a Store stub on this PC.
  - The old suite has 85 tests, not 68 as the phase file and CLAUDE.md say.
  - How the tests changed in the port:
    - `unittest` classes became pytest functions, with `tmp_path` in place of `tempfile.mkdtemp`;
    - fixture JSON is now read with explicit `encoding="utf-8"`;
    - the name tests came from `tests/test_queries.py::ProjectNameTests`, since there was no standalone names test;
    - only the pure `_session_title` part of `test_scanner_titles.py` was ported, because its scan/SQLite part belongs to phase 01's ingest;
    - added tests: `tool_use_id` on both row kinds, uniform tool-row keys, the `_tier_from_name` cases, `best_project_name`, `config` and the CLI.
- **Notes for the next session:**
  - `collector/parse.py` has no `_project_slug` helper and no file walking. Port `_project_slug`, `scan_file`'s partial-line guard and `scan_dir`'s mtime/offset skip logic into `collector/ingest.py`.
  - Get config via `claude_lens.config.load_settings()`. It loads the repo-root `.env.local` into `os.environ` (never overriding real vars) and returns `Settings`: `database_url`, `db_schema`, `machine`, `claude_projects_dir`, and so on.
  - For test schemas, `Settings.from_env({..., "DB_SCHEMA": "claude_lens_test_<hex>"})` passes validation.
  - `load_pricing()` defaults to `backend/pricing.json` via `DEFAULT_PRICING_PATH`.
  - Add `psycopg.sql` / `Identifier` usage for the schema; don't f-string it.
