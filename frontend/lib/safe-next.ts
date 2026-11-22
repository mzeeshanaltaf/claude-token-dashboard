export const DEFAULT_AFTER_LOGIN = "/overview";

/**
 * The post-login destination from `?next=`, limited to same-origin paths so
 * the login page can't be used as an open redirect.
 */
export function safeNext(next: string | null | undefined): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) {
    return DEFAULT_AFTER_LOGIN;
  }
  if (next === "/login" || next.startsWith("/login?") || next.startsWith("/login/")) {
    return DEFAULT_AFTER_LOGIN;
  }
  return next;
}
