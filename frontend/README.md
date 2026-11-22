# Claude Lens frontend

Next.js 16 (App Router, Cache Components) + React 19 + shadcn/ui (radix, nova) + Tailwind v4 + TanStack Query.

## Run

```bash
# backend first, from backend/ (COOKIE_SECURE=false for http://localhost)
COOKIE_SECURE=false TRUST_PROXY=true uv run uvicorn claude_lens.api.main:app --port 8000

# then, from frontend/
pnpm install
pnpm dev            # http://localhost:3000
pnpm lint && pnpm build
pnpm gen:api        # regenerate lib/api-types.ts from http://localhost:8000/openapi.json
```

`BACKEND_URL` (default `http://localhost:8000`) is read **at request time** by the API proxy, never at build time.

## How it fits together

- `app/api/[...path]/route.ts`: the same-origin proxy to `${BACKEND_URL}/api/*`. It forwards the cookie, content-type, origin and x-forwarded-for, sets x-forwarded-host/-proto to the public host, streams the body both ways, and copies every `set-cookie`.
- `proxy.ts` (Next 16's name for middleware): sends a request with no `cl_session` cookie to `/login?next=…`, and sends `/login` with a cookie to `/`. It only checks that the cookie exists; the backend validates the session.
- `app/login/`: a progressive-enhancement form. When hydrated it uses `fetch`. Without JS it posts natively to `/login/submit`, which re-sends the credentials as JSON (the backend's CSRF guard needs JSON) and answers with a 303. The page sets `instant = false`, so it renders per request and the no-JS HTML carries `next` and the error message.
- `app/(dashboard)/`: the signed-in shell (sidebar and top bar). Pages fetch their data in the browser with TanStack Query, so the server renders the frame and skeletons.

## Conventions

- **Folders:** `components/ui/` holds the shadcn components (edit sparingly and mark local changes with a `Claude Lens:` comment). `components/shell/` is the app frame. `components/*.tsx` are shared pieces (`kpi-card`, `empty-state`, `error-state`, `loading`). `lib/` holds non-UI code and `hooks/` the React hooks.
- **API:** use `api.get/post` from `lib/api.ts`, typed from `lib/api-types.ts`. A 401 clears the cookie and goes to `/login?next=…`. In components, prefer `useRangedQuery(path, query)` (date-ranged endpoints; the range key is part of the query key) or `useApiQuery(path)` from `lib/queries.ts`.
- **Date range:** the URL is the source of truth (`?range=7d|30d|90d|all` or `?since=YYYY-MM-DD&until=YYYY-MM-DD`). The last choice is remembered in localStorage (`lens.range`). `rangeToApi()` turns it into ISO `since`/`until` at local midnight when the request is made. Any component that calls `useRange` needs a `<Suspense>` above it (Cache Components).
- **Hydration:** anything that reads browser-only state while rendering (localStorage, the clock, the platform) is either mounted with `next/dynamic({ ssr: false })` (`components/shell/client-only.tsx`) or read through `useSyncExternalStore` with a fixed server snapshot.
- **Colours:** only use tokens. Charts take their colours from CSS variables via `lib/chart-colors.ts` (`tokenChartConfig`, `familyChartConfig`): `--chart-input`, `--chart-output`, `--chart-cache-write`, `--chart-cache-read`, and `--family-{opus,sonnet,fable,haiku,mythos}`. The hues are the same in both themes; dark mode uses darker steps that pass the dataviz palette validator. Status colours are `text-success`, `text-warning` and `text-destructive`.
- **Privacy:** add `blur-sensitive` to anything personal (prompt text, project names, paths, titles). Ctrl/Cmd+B toggles `body.privacy-on`. The sidebar's own shortcut moved to Ctrl/Cmd+\\.
- **Formatting:** use `fmt` from `lib/format.ts` and `parseClaudeModel` from `lib/models.ts`. Numbers use `font-mono tabular`.

## Page patterns (phase 05)

Each page lives in `components/<page>/…-page.tsx`; `app/(dashboard)/<route>/page.tsx` only sets `metadata` and renders it.

- **Page state in the URL.** Sort, page, page size and filters sit next to the range params: `hooks/use-url-state.ts` (`useUrlState`, `useDebouncedUrlParam` for search boxes, `useRangedHref` for links that keep the range). Server-paginated tables use `hooks/use-server-table.ts` (`?sort=&order=&page=&size=`, plus `useClampPage` to go back to page 1 when a filter empties the page).
- **Tables:** `components/data-table.tsx` (TanStack Table **v8**). Pass `server={t.table(total)}` for server sorting/paging (column `id` = the API's sort key; display-only columns are fine, a no-op accessor is added) or nothing for client sorting (columns need an `accessorFn`), with `clientPageSize` for client paging. `meta: { numeric, info, className }` right-aligns numbers and adds an (i) to the header. `onRowClick` makes rows clickable and keyboard-focusable.
- **Filters:** `components/filters.tsx` (`FilterBar`, `SearchBox` → `?q=`, `ProjectSelect` → `?project=`, `ModelSelect` → `?model=`). One filter row above what it scopes.
- **Charts** (`components/charts/`): `TokenComposition` (tall segmented bar, tokens/cost switch), `DailyChart` (Tokens/Cost × Chart/Table; takes `/api/daily` rows, also with `?project=`), `ModelMix` (donut + version list). Ranked bars are HTML: `components/bar-list.tsx`. Table-row trends: `components/sparkline.tsx` (SVG, no Recharts). Shape data with `lib/usage.ts` (`modelTree`, `fillDaily`, `cacheHitRate`, `coreTokens`).
- **Charts follow the dataviz rules:** every chart has a legend for ≥ 2 series, a table view or printed values (so tooltips never gate a number), recessive grid, bars ≤ 24px with a 4px rounded end, and a Recharts legend with `itemSorter={null}` (stack order, not alphabetical). Dark mode has its **own validated steps** of the data colours (`.dark` in `app/globals.css`).
- **Definitions:** `lib/glossary.ts` (the old "What do these numbers mean?" wording) via `<InfoTip term="cacheRead" />` or a column's `meta.info`.
- **Detail pages** (`/sessions/[id]`, `/projects/[slug]`) read the param with `useParams()` in a client component; the dashboard layout's `<Suspense>` makes them `◐` (static shell). On dynamic routes **`usePathname()` is URL data too**: only call it inside a `<Suspense>` (see `components/shell/top-bar.tsx`, `app-sidebar.tsx`), or the build fails.
- **Refetches** keep the previous data (`placeholderData`); pass `dim={q.isPlaceholderData}` to `SectionCard`/`DataTable` to fade it instead of flashing skeletons.
- **Mutations** with an undo: see `components/tips/tips-page.tsx` (optimistic `setQueryData`, a sonner toast with an Undo action).
