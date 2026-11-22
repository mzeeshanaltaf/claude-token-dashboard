import "server-only";

/** The FastAPI backend, read at request time (never inlined at build). */
export function backendUrl(): string {
  return (process.env.BACKEND_URL || "http://localhost:8000").replace(/\/+$/, "");
}

/**
 * Headers that tell the backend who the real client is and which public host
 * the browser used (its CSRF guard compares `Origin` against
 * `X-Forwarded-Host`; with TRUST_PROXY=true the lockout keys on the last
 * `X-Forwarded-For` hop).
 */
export function forwardedHeaders(req: Request): Headers {
  const h = new Headers();
  const url = new URL(req.url);
  for (const name of ["cookie", "origin", "user-agent", "x-forwarded-for"]) {
    const v = req.headers.get(name);
    if (v) h.set(name, v);
  }
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host");
  if (host) h.set("x-forwarded-host", host);
  h.set("x-forwarded-proto", req.headers.get("x-forwarded-proto") ?? url.protocol.replace(":", ""));
  return h;
}
