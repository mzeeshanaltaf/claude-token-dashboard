/**
 * A script that runs while the browser parses the server HTML, before first
 * paint, to correct the DOM from client-only state (a cookie, localStorage).
 * See node_modules/next/dist/docs/01-app/02-guides/preventing-flash-before-hydration.md.
 *
 * On the client it renders as `text/plain`, so React doesn't warn about
 * rendering a script and a client-side render never runs it again; the
 * component that owns the state reads the same source in a lazy initializer.
 * The element it corrects needs `suppressHydrationWarning`.
 */
export function InlineScript({ html }: { html: string }) {
  return (
    <script
      type={typeof window === "undefined" ? "text/javascript" : "text/plain"}
      suppressHydrationWarning
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
