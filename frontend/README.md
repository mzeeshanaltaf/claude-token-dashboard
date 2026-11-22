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
- **Colours:** only use tokens. Charts take their colours from CSS variables via `lib/chart-colors.ts` (`tokenChartConfig`, `familyChartConfig`): `--chart-input`, `--chart-output`, `--chart-cache-write`, `--chart-cache-read`, and `--family-{opus,sonnet,fable,haiku,mythos}`. Status colours are `text-success`, `text-warning` and `text-destructive`.
- **Privacy:** add `blur-sensitive` to anything personal (prompt text, project names, paths, titles). Ctrl/Cmd+B toggles `body.privacy-on`. The sidebar's own shortcut moved to Ctrl/Cmd+\\.
- **Formatting:** use `fmt` from `lib/format.ts` and `parseClaudeModel` from `lib/models.ts`. Numbers use `font-mono tabular`.
