/** Claude model families, in display order. Colours live in globals.css. */
export const MODEL_FAMILIES = ["opus", "sonnet", "fable", "haiku", "mythos"] as const;
export type ModelFamily = (typeof MODEL_FAMILIES)[number];

export const FAMILY_LABELS: Record<ModelFamily, string> = {
  opus: "Opus",
  sonnet: "Sonnet",
  fable: "Fable",
  haiku: "Haiku",
  mythos: "Mythos",
};

export interface ParsedModel {
  family: ModelFamily;
  /** "5.5", "4.5", "3.5"; "" when the id carries no version. */
  version: string;
}

function isFamily(s: string): s is ModelFamily {
  return (MODEL_FAMILIES as readonly string[]).includes(s);
}

/**
 * "claude-opus-5-5" → { family: "opus", version: "5.5" }.
 *
 * Ported from web/routes/overview.js. Handles dated ids
 * ("claude-haiku-4-5-20251001") and the legacy order ("claude-3-5-sonnet-…").
 * Non-Claude models (e.g. a local gemma) and "<synthetic>" return null.
 */
export function parseClaudeModel(id: string | null | undefined): ParsedModel | null {
  if (!id || !id.startsWith("claude-")) return null;
  const parts = id
    .slice("claude-".length)
    .split("-")
    .filter((p) => !/^\d{8}$/.test(p));
  const family = parts.find(isFamily);
  if (!family) return null;
  return { family, version: parts.filter((p) => /^\d+$/.test(p)).join(".") };
}
