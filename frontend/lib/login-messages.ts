/** Login error codes, shared by the no-JS redirect (`?error=`) and the fetch path. */
export type LoginErrorCode = "invalid" | "missing" | "locked" | "server";

export function loginErrorMessage(code: string | null | undefined, retryAfterSeconds?: number | null): string | null {
  switch (code) {
    case null:
    case undefined:
    case "":
      return null;
    case "invalid":
      return "Wrong username or password.";
    case "missing":
      return "Enter your username and password.";
    case "locked": {
      const mins = retryAfterSeconds ? Math.max(1, Math.ceil(retryAfterSeconds / 60)) : null;
      return mins
        ? `Too many failed attempts. Try again in ${mins} minute${mins === 1 ? "" : "s"}.`
        : "Too many failed attempts. Try again in a few minutes.";
    }
    default:
      return "Couldn't sign in right now. Check that the server is running and try again.";
  }
}
