import { ImageResponse } from "next/og";

/** Branded social card: ink field, serif promise, accent underline. Rendered
 *  once at build time. */

export const alt = "Ada — the career agent that gets you hired";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const INK = "#17150f";
const PAPER = "#faf9f6";
const MUTED = "#a09a8c";
const ACCENT = "#8b85f4";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: INK,
          color: PAPER,
          padding: "64px 72px",
          fontFamily: "Georgia, serif",
        }}
      >
        <div style={{ display: "flex", fontSize: 44 }}>
          <span>Ada</span>
          <span style={{ color: ACCENT }}>.</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", fontSize: 100, lineHeight: 1.05 }}>
            <span>She gets you&nbsp;</span>
            <span style={{ display: "flex", flexDirection: "column", color: ACCENT }}>
              <span style={{ fontStyle: "italic" }}>hired.</span>
              <div
                style={{
                  display: "flex",
                  width: "92%",
                  height: 7,
                  marginTop: 2,
                  borderRadius: 4,
                  background: ACCENT,
                }}
              />
            </span>
          </div>
          <div
            style={{
              display: "flex",
              marginTop: 34,
              fontSize: 30,
              color: MUTED,
              fontFamily: "sans-serif",
            }}
          >
            CV rewrite · ranked job matches · scored mock interview — one autonomous run.
          </div>
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: 24,
            color: MUTED,
            fontFamily: "sans-serif",
          }}
        >
          <span>₦2,000 / $15 per run · or go unlimited</span>
          <span>For every career</span>
        </div>
      </div>
    ),
    { ...size },
  );
}
