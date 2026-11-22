/**
 * Auth gate (Next 16 renamed middleware.ts to proxy.ts).
 *
 * An optimistic check on the presence of the `cl_session` cookie only: the
 * backend validates the session on every API call, and a stale cookie is
 * caught by lib/api.ts (a 401 sends the browser to /login).
 */
import { NextResponse, type NextRequest } from "next/server";

const SESSION_COOKIE = "cl_session";

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const signedIn = request.cookies.has(SESSION_COOKIE);
  const isLogin = pathname === "/login" || pathname.startsWith("/login/");

  if (isLogin) {
    // /login/submit is the no-JS form target; let it through either way.
    if (signedIn && pathname === "/login") {
      return NextResponse.redirect(new URL("/", request.url));
    }
    return NextResponse.next();
  }

  if (!signedIn) {
    const url = new URL("/login", request.url);
    const next = pathname + search;
    if (next !== "/") url.searchParams.set("next", next);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  // Pages only: not the API proxy, Next internals or static files.
  matcher: ["/((?!api/|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|txt|xml)$).*)"],
};
