/**
 * The old Overview's "What do these numbers mean?" block, one entry per term,
 * worded as it was (web/routes/overview.js). Each one is shown as an info
 * tooltip on its metric (`<InfoTip term="cacheRead" />`).
 */
export const GLOSSARY = {
  session:
    "One run of Claude Code (from `claude` to exit). Each session is a single .jsonl file.",
  turn: "One message you sent to Claude. Each turn triggers a response (possibly with tool calls in between).",
  input: "The new text you (and tool results) sent to Claude this turn. Billed at the full input rate.",
  output: "The text Claude wrote back. Billed at the highest rate — usually the biggest cost driver per turn.",
  cacheRead:
    "Tokens Claude re-used from a cache (your CLAUDE.md, previously-read files, the conversation so far). ~10× cheaper than fresh input. High cache-read counts = good cost hygiene.",
  cacheCreate: "Writing something into the cache for the first time. One-time cost; pays off on the next turn.",
  totalTokens:
    "Every token that moved: Input + Output + Cache read + Cache create. This includes cache reads, so it's much larger than core tokens (cache reads usually dominate). Useful as a raw volume measure, not a cost measure.",
  coreTokens:
    "Input + Output + Cache create — a proxy for where your spend concentrates. Cache reads are billed too (about 10× cheaper), but they're excluded from this count because their sheer volume would swamp it. For actual spend see Est. cost; for raw volume see Total tokens.",
  // New in Claude Lens.
  estCost:
    "What these tokens would cost at API rates (pricing.json), across all five token types. On a subscription plan this is the value you got, not what you paid.",
  cacheHitRate:
    "Cache read ÷ (cache read + input + cache create): the share of the prompt tokens Claude read from cache instead of processing fresh. Higher is cheaper.",
} as const;

export type GlossaryTerm = keyof typeof GLOSSARY;
