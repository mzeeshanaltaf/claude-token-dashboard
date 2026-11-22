import type { Metadata } from "next";

import { LoginForm } from "@/components/login-form";
import { LogoMark, Wordmark } from "@/components/logo";
import { loginErrorMessage } from "@/lib/login-messages";

export const metadata: Metadata = { title: "Sign in" };

/**
 * Render the whole page per request, blocking on searchParams. With Cache
 * Components the default would be a prerendered shell plus streamed content,
 * and swapping streamed content in needs JavaScript: the no-JS fallback would
 * lose `?next=` and the `?error=` message.
 */
export const instant = false;

function first(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const sp = await searchParams;
  const retry = Number(first(sp.retry));
  return (
    <main className="lens-glow relative grid min-h-svh place-items-center px-4 py-10">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <div className="flex flex-col items-center gap-3 text-center">
          <LogoMark className="size-11 drop-shadow-[0_0_18px_rgba(74,158,255,0.35)]" />
          <div className="flex flex-col gap-1">
            <Wordmark className="text-xl" />
            <p className="text-sm text-muted-foreground">Usage, cost &amp; workflow analytics for Claude Code</p>
          </div>
        </div>
        <LoginForm
          next={first(sp.next) ?? ""}
          initialError={loginErrorMessage(first(sp.error), Number.isFinite(retry) ? retry : null)}
        />
      </div>
    </main>
  );
}
