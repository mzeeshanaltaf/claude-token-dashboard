/**
 * Typed fetch wrapper over the backend, reached through the same-origin
 * `/api/*` proxy (app/api/[...path]/route.ts).
 *
 * Types come from the backend's OpenAPI schema (`pnpm gen:api` regenerates
 * lib/api-types.ts with the backend running on :8000).
 */
import type { paths } from "./api-types";

type Method = "get" | "post" | "put" | "delete";

type PathsWith<M extends Method> = {
  [P in keyof paths]: paths[P][M] extends never | undefined ? never : P;
}[keyof paths];

export type GetPath = PathsWith<"get">;
export type PostPath = PathsWith<"post">;

type Operation<P extends keyof paths, M extends Method> = NonNullable<paths[P][M]>;

type JsonContent<R> = R extends { content: { "application/json": infer T } } ? T : never;

/** The 200 JSON body of `METHOD path`. */
export type ApiResponse<P extends keyof paths, M extends Method = "get"> =
  Operation<P, M> extends { responses: { 200: infer R } } ? JsonContent<R> : never;

/** The query parameters of `METHOD path`. */
export type ApiQuery<P extends keyof paths, M extends Method = "get"> =
  Operation<P, M> extends { parameters: { query?: infer Q } } ? Q : never;

/** The JSON request body of `METHOD path`. */
export type ApiBody<P extends keyof paths, M extends Method = "post"> =
  Operation<P, M> extends { requestBody: infer B } ? JsonContent<NonNullable<B>> : never;

/** Schema shortcut: `Schema<"Overview">`. */
export type Schema<K extends keyof import("./api-types").components["schemas"]> =
  import("./api-types").components["schemas"][K];

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
    /** Seconds, from the `Retry-After` header of a 429. */
    readonly retryAfter: number | null = null,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

type QueryValue = string | number | boolean | null | undefined | readonly (string | number)[];

export interface RequestOptions {
  query?: Record<string, QueryValue> | object;
  /** Values for `{name}` placeholders in the path. */
  params?: Record<string, string | number>;
  signal?: AbortSignal;
  /** Default true: a 401 sends the browser to /login?next=<current page>. */
  redirectOn401?: boolean;
}

function buildUrl(path: string, opts: RequestOptions): string {
  const url = path.replace(/\{(\w+)\}/g, (_, name: string) => {
    const v = opts.params?.[name];
    if (v === undefined) throw new Error(`missing path param "${name}" for ${path}`);
    return encodeURIComponent(String(v));
  });
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries((opts.query ?? {}) as Record<string, QueryValue>)) {
    if (v === null || v === undefined || v === "") continue;
    if (Array.isArray(v)) v.forEach((item) => qs.append(k, String(item)));
    else qs.set(k, String(v));
  }
  const s = qs.toString();
  return s ? `${url}?${s}` : url;
}

export function loginUrl(next?: string): string {
  return next && next !== "/" ? `/login?next=${encodeURIComponent(next)}` : "/login";
}

let redirecting = false;

/**
 * A 401 with a cookie still present means the session expired or was revoked.
 * Clear the cookie first (logout always succeeds), or proxy.ts would bounce
 * /login straight back to the dashboard.
 */
function redirectToLogin() {
  if (typeof window === "undefined" || window.location.pathname === "/login" || redirecting) return;
  redirecting = true;
  const next = window.location.pathname + window.location.search;
  fetch("/api/auth/logout", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: "{}",
    credentials: "same-origin",
  })
    .catch(() => undefined)
    .finally(() => window.location.assign(loginUrl(next)));
}

async function errorFrom(res: Response): Promise<ApiError> {
  let detail = res.statusText || `HTTP ${res.status}`;
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") detail = body.detail;
    else if (Array.isArray(body?.detail)) detail = body.detail.map((d: { msg?: string }) => d.msg).join("; ");
  } catch {
    /* not JSON */
  }
  const ra = Number(res.headers.get("retry-after"));
  return new ApiError(res.status, detail, Number.isFinite(ra) && ra > 0 ? ra : null);
}

async function request<T>(method: string, path: string, body: unknown, opts: RequestOptions = {}): Promise<T> {
  const res = await fetch(buildUrl(path, opts), {
    method,
    // The backend's CSRF guard requires JSON on every non-GET request.
    headers: method === "GET" ? { accept: "application/json" } : { "content-type": "application/json", accept: "application/json" },
    body: method === "GET" ? undefined : JSON.stringify(body ?? {}),
    credentials: "same-origin",
    cache: "no-store",
    signal: opts.signal,
  });
  if (res.status === 401 && opts.redirectOn401 !== false) redirectToLogin();
  if (!res.ok) throw await errorFrom(res);
  return (await res.json()) as T;
}

export const api = {
  get<P extends GetPath>(path: P, opts?: RequestOptions & { query?: ApiQuery<P> }) {
    return request<ApiResponse<P>>("GET", path, undefined, opts);
  },
  post<P extends PostPath>(path: P, body: ApiBody<P> | Record<string, never>, opts?: RequestOptions) {
    return request<ApiResponse<P, "post">>("POST", path, body, opts);
  },
};
