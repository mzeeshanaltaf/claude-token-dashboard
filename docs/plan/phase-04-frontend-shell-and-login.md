# Phase 04: Frontend shell & login

**Goal:** scaffold the Next.js + shadcn app in `frontend/` with:
- the runtime API proxy;
- the login page and auth redirects;
- the app shell (sidebar, top bar, date-range picker, privacy blur, sync badge, user menu);
- shared formatting and chart utilities.

The pages themselves come in phase 05. Each page here is a placeholder that fetches one endpoint, to prove the data flows end to end.

## Entry criteria

- Phase 03 is `done`, and the backend runs locally on :8000 with login working.

## Environment check

```bash
cd backend && uv run uvicorn claude_lens.api.main:app --port 8000   # leave running
node --version && pnpm --version
```

## Read first

- `web/app.js`: `fmt` helpers, the range preference, the privacy blur (Ctrl/Cmd+B toggles `body.privacy-on`, and elements marked `.blur-sensitive` get blurred), the first-run plan picker
- `web/style.css`: the current palette (`#4A9EFF` input, `#7C5CFF` output, `#E8A23B` cache create, `#3FB68B` cache read) and the model-family colours in `web/routes/overview.js:7-13`
- The user's global CLAUDE.md hydration rule (summarised in README.md "Facts")
- Use the `shadcn`, `nextjs-best-practices` and `vercel-react-best-practices` skills. Use `frontend-design`/`impeccable` for visual direction.

## Tasks

- [ ] Scaffold with the latest stable Next.js: App Router, TypeScript, Tailwind v4, ESLint, pnpm, `src/` optional. Set `output: "standalone"` in `next.config`.
- [ ] Run `shadcn init`, then add: sidebar, card, button, input, label, table, tabs, badge, tooltip, dropdown-menu, dialog, sheet, command, select, skeleton, sonner, chart, separator, avatar, scroll-area, toggle-group, popover, calendar.
- [ ] `next-themes`: dark by default, light available. Define design tokens in CSS variables. Keep the token-type colours above as chart tokens (`--chart-input`, `--chart-output`, `--chart-cache-read`, `--chart-cache-write`) and the family colours (opus, sonnet, fable, haiku, mythos).
- [ ] **API proxy** `app/api/[...path]/route.ts`:
  - forward GET, POST, PUT and DELETE to `process.env.BACKEND_URL` (default `http://localhost:8000`) **at runtime** (`dynamic = "force-dynamic"`);
  - pass the `cookie` request header through, plus every `set-cookie` response header;
  - forward `x-forwarded-for`, `x-forwarded-host` and `origin`;
  - stream the body, which CSV export in phase 06 needs.
- [ ] Auth gate in `middleware.ts` (`proxy.ts` if the installed Next version uses that name):
  - a request without a `cl_session` cookie on any page except `/login` redirects to `/login?next=…`;
  - `/login` with a cookie redirects to `/`.
- [ ] `lib/api.ts`: a typed fetch wrapper. A 401 redirects to `/login`. Generate the TS types from the backend OpenAPI (`openapi-typescript`) into `lib/api-types.ts`, and add a `pnpm gen:api` script.
- [ ] TanStack Query provider. Query keys include the active date range.
- [ ] **Login page** `/login`:
  - a centred shadcn card with the Claude Lens logo, username, password and "Sign in";
  - error and lockout (429) messages;
  - redirect to `next` on success.
  - Follow the `nextjs-progressive-form` skill so the form still works if hydration fails.
- [ ] **App shell** (`app/(dashboard)/layout.tsx`):
  - **Sidebar** (collapsible, icons and labels): Overview · Activity · Prompts · Sessions · Projects · Tools · Skills · Tips · Settings.
  - **Top bar:**
    - page title;
    - **date-range picker** (7d, 30d, 90d, All, custom from/to), stored in the URL query (`?range=` / `?since=&until=`) so it's shareable, with the last choice remembered in localStorage;
    - Cmd+K button (opens an empty command dialog for now; phase 06 fills it);
    - **Synced badge** from `/api/sync-status` ("Synced 5h ago", amber after 36h, red on error, with the machine name in a tooltip);
    - **privacy-blur toggle** (Ctrl/Cmd+B, a `.blur-sensitive` utility);
    - user menu (Change password → Settings, Log out).
  - Mount the client-only pieces (range from localStorage, relative times) with `next/dynamic({ ssr:false })` **as the global CLAUDE.md requires**.
- [ ] Port the `fmt` helpers to `lib/format.ts` (int, compact, usd, pct, ts, tsTime, modelShort, modelFamily). Port `parseClaudeModel` from `web/routes/overview.js:18-24` to `lib/models.ts`.
- [ ] Shared UI pieces:
  - `components/kpi-card.tsx` (label, value, sub-value, optional sparkline, info tooltip);
  - `components/empty-state.tsx` and `components/error-state.tsx`;
  - loading skeletons.
- [ ] Create a placeholder for each route that renders one real number from its endpoint.
- [ ] **First-run plan picker:** if `settings.plan` isn't set, show a dialog once (it replaces the old `firstRun` in `web/app.js`).

## Exit criteria

- `pnpm lint && pnpm build` pass with no type errors.
- With `pnpm dev` and the backend running:
  - opening `/overview` signed out redirects to `/login`; signing in reaches the shell;
  - a placeholder page shows real data, and changing the range re-fetches;
  - logging out returns to `/login`, and the cookie is cleared;
  - Ctrl+B blurs the elements marked as sensitive;
  - **no hydration warnings** in the browser console.

## Handoff notes to capture

- The Next.js, React and shadcn versions installed; whether it's `middleware.ts` or `proxy.ts`.
- The component conventions you settled on (folder layout, how charts take their colours).
