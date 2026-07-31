// Shareable CV-score card, encoded straight into the URL — no server round-trip, so the
// link previews (WhatsApp, X, LinkedIn) and the landing page render from the same payload.
// Kept tiny and clamped: a self-reported brag card carries only a score and an optional role.

export interface ShareCard {
  score: number; // 0–100
  role?: string; // optional target role, short
}

function toB64Url(s: string): string {
  const b64 = typeof btoa !== "undefined" ? btoa(s) : Buffer.from(s, "utf8").toString("base64");
  return b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromB64Url(s: string): string {
  const b64 = s.replace(/-/g, "+").replace(/_/g, "/");
  return typeof atob !== "undefined"
    ? atob(b64)
    : Buffer.from(b64, "base64").toString("utf8");
}

export function encodeCard(card: ShareCard): string {
  const clean: ShareCard = { score: clampScore(card.score) };
  if (card.role) clean.role = card.role.slice(0, 48);
  return toB64Url(JSON.stringify(clean));
}

/** Decode a share token, defensively. Returns null on anything malformed. */
export function decodeCard(token: string): ShareCard | null {
  try {
    const parsed = JSON.parse(fromB64Url(token)) as Partial<ShareCard>;
    if (typeof parsed.score !== "number" || Number.isNaN(parsed.score)) return null;
    const role = typeof parsed.role === "string" ? parsed.role.slice(0, 48) : undefined;
    return { score: clampScore(parsed.score), role };
  } catch {
    return null;
  }
}

function clampScore(n: number): number {
  return Math.max(0, Math.min(100, Math.round(n)));
}

/** The headline verdict shown on the card, keyed off the score band. */
export function verdict(score: number): string {
  if (score >= 85) return "Interview-ready";
  if (score >= 70) return "Strong, a few tweaks away";
  if (score >= 50) return "Solid base to build on";
  return "Worth a rework";
}
