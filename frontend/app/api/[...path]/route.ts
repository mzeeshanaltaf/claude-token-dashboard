/**
 * Same-origin proxy: /api/* → ${BACKEND_URL}/api/*, resolved at request time
 * so the backend URL is never baked into the build.
 *
 * - Request: forwards cookie, content-type, accept, origin, user-agent and
 *   x-forwarded-for; sets x-forwarded-host/-proto to the public host so the
 *   backend's CSRF Origin check compares against what the browser saw.
 * - Response: streams the body through (CSV export) and copies every
 *   set-cookie header individually.
 */
import { connection, type NextRequest } from "next/server";

import { backendUrl, forwardedHeaders } from "@/lib/backend";

// Hop-by-hop headers, plus the ones that stop matching once fetch() has
// decoded the upstream body.
const DROP_RESPONSE_HEADERS = new Set([
  "connection",
  "keep-alive",
  "transfer-encoding",
  "content-encoding",
  "content-length",
  "set-cookie",
  "upgrade",
]);

async function proxy(req: NextRequest, ctx: RouteContext<"/api/[...path]">): Promise<Response> {
  // Opt out of prerendering: read env and the request at runtime only.
  // (`dynamic = "force-dynamic"` is not allowed with cacheComponents.)
  await connection();
  const { path } = await ctx.params;
  if (path.some((seg) => seg === "" || seg === "." || seg === "..")) {
    return Response.json({ detail: "Not Found" }, { status: 404 });
  }
  const target = `${backendUrl()}/api/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;

  const headers = forwardedHeaders(req);
  for (const name of ["accept", "content-type"]) {
    const value = req.headers.get(name);
    if (value) headers.set(name, value);
  }

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: req.method,
      headers,
      body: hasBody ? req.body : undefined,
      // Required by Node's fetch to stream a request body.
      ...(hasBody ? { duplex: "half" } : {}),
      redirect: "manual",
      cache: "no-store",
      signal: req.signal,
    } as RequestInit);
  } catch (err) {
    if (req.signal.aborted) return new Response(null, { status: 499 });
    console.error(`[api proxy] ${req.method} /api/${path.join("/")} failed:`, err);
    return Response.json({ detail: "Backend unavailable" }, { status: 502 });
  }

  const out = new Headers();
  upstream.headers.forEach((value, name) => {
    if (!DROP_RESPONSE_HEADERS.has(name.toLowerCase())) out.set(name, value);
  });
  for (const cookie of upstream.headers.getSetCookie()) out.append("set-cookie", cookie);
  if (!out.has("cache-control")) out.set("cache-control", "no-store");

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: out,
  });
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE };
