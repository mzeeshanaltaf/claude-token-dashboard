/**
 * No-JS fallback for the login form (progressive enhancement).
 *
 * A native <form method="post"> sends application/x-www-form-urlencoded,
 * which the backend's CSRF guard rejects (415). This handler re-sends the
 * credentials as JSON, passes the session cookie back, and answers with a
 * 303 so the browser follows up with a GET. The browser's own `Origin` is
 * forwarded, so the backend's cross-origin check still applies.
 */
import { connection, NextResponse, type NextRequest } from "next/server";

import { backendUrl, forwardedHeaders } from "@/lib/backend";
import { safeNext } from "@/lib/safe-next";

function backToLogin(req: NextRequest, error: string, next: string, retryAfter?: string | null) {
  const url = new URL("/login", req.url);
  url.searchParams.set("error", error);
  if (retryAfter) url.searchParams.set("retry", retryAfter);
  if (next) url.searchParams.set("next", next);
  return NextResponse.redirect(url, 303);
}

export async function POST(req: NextRequest) {
  await connection();
  let form: FormData;
  try {
    form = await req.formData();
  } catch {
    return backToLogin(req, "invalid", "");
  }
  const username = String(form.get("username") ?? "");
  const password = String(form.get("password") ?? "");
  const rawNext = String(form.get("next") ?? "");
  if (!username || !password) return backToLogin(req, "missing", rawNext);

  const headers = forwardedHeaders(req);
  headers.set("content-type", "application/json");
  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}/api/auth/login`, {
      method: "POST",
      headers,
      body: JSON.stringify({ username, password }),
      cache: "no-store",
    });
  } catch {
    return backToLogin(req, "server", rawNext);
  }

  if (upstream.ok) {
    const res = NextResponse.redirect(new URL(safeNext(rawNext), req.url), 303);
    for (const cookie of upstream.headers.getSetCookie()) res.headers.append("set-cookie", cookie);
    return res;
  }
  if (upstream.status === 429) return backToLogin(req, "locked", rawNext, upstream.headers.get("retry-after"));
  if (upstream.status === 401 || upstream.status === 422) return backToLogin(req, "invalid", rawNext);
  return backToLogin(req, "server", rawNext);
}
