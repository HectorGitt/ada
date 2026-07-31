import { ImageResponse } from "next/og";

import { decodeCard, verdict } from "@/lib/share";

export const runtime = "nodejs";
export const alt = "My CV readiness score from Ada";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// The link-preview card. Rendered from the URL payload alone — no data fetch — so it
// unfurls instantly wherever the link is pasted. Satori requires an explicit `display`
// on every element with more than one child, so each container sets it.
export default async function Image({ params }: { params: Promise<{ card: string }> }) {
  const { card } = await params;
  const data = decodeCard(card) ?? { score: 0 };
  const ink = "#1a1714";
  const paper = "#faf9f6";
  const accent = "#4f46e5";
  const muted = "#8a8377";

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: paper,
          padding: "72px 80px",
          fontFamily: "sans-serif",
          color: ink,
        }}
      >
        <div style={{ display: "flex", fontSize: 34, fontWeight: 700 }}>
          <span>Ada</span>
          <span style={{ color: accent }}>.</span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 64 }}>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              width: 300,
              height: 300,
              borderRadius: 300,
              border: `16px solid ${accent}`,
            }}
          >
            <div style={{ display: "flex", fontSize: 132, fontWeight: 800 }}>
              <span>{String(data.score)}</span>
            </div>
            <div style={{ display: "flex", fontSize: 30, color: muted }}>
              <span>out of 100</span>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", maxWidth: 620 }}>
            <div style={{ display: "flex", fontSize: 30, color: muted }}>
              <span>My CV readiness</span>
            </div>
            <div style={{ display: "flex", fontSize: 68, fontWeight: 700, marginTop: 8 }}>
              <span>{verdict(data.score)}</span>
            </div>
            {data.role ? (
              <div style={{ display: "flex", fontSize: 32, color: muted, marginTop: 16 }}>
                <span>for {data.role}</span>
              </div>
            ) : null}
          </div>
        </div>

        <div style={{ display: "flex", fontSize: 30, color: accent, fontWeight: 600 }}>
          <span>Check your own CV free — no signup →</span>
        </div>
      </div>
    ),
    size,
  );
}
