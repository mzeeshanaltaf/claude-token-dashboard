import { useId } from "react";

import { cn } from "@/lib/utils";

/**
 * The Claude Lens mark: the old dashboard's blue→violet tile and rising bars,
 * seen through a lens ring.
 */
export function LogoMark({ className }: { className?: string }) {
  const id = useId();
  const grad = `${id}-g`;
  const clip = `${id}-c`;
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className={cn("size-7 shrink-0", className)}>
      <defs>
        <linearGradient id={grad} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#4A9EFF" />
          <stop offset="1" stopColor="#7C5CFF" />
        </linearGradient>
        <clipPath id={clip}>
          <circle cx="16" cy="16" r="8.25" />
        </clipPath>
      </defs>
      <rect width="32" height="32" rx="8" fill={`url(#${grad})`} />
      <circle cx="16" cy="16" r="10" fill="none" stroke="#fff" strokeOpacity="0.95" strokeWidth="2" />
      <g clipPath={`url(#${clip})`} fill="#fff">
        <rect x="9.5" y="17.5" width="3.4" height="9" rx="1" opacity="0.7" />
        <rect x="14.3" y="13.5" width="3.4" height="13" rx="1" opacity="0.85" />
        <rect x="19.1" y="9.5" width="3.4" height="17" rx="1" />
      </g>
      <path d="M9.6 11.2a7.6 7.6 0 0 1 4.2-3.3" fill="none" stroke="#fff" strokeOpacity="0.55" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("font-semibold tracking-tight", className)}>
      Claude <span className="text-primary">Lens</span>
    </span>
  );
}
