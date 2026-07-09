import { ImageResponse } from "next/og";

export const OG_SIZE = { width: 1200, height: 630 };

/** One branded OG template for every page: paper card, Steel Blue bar,
 *  Varuflow wordmark, injected title + subtitle. Flat — no gradients. */
export function renderOg(title: string, subtitle: string) {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          background: "#ffffff",
          padding: 72,
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ width: 28, height: 28, background: "#2f5ea8", borderRadius: 8 }} />
          <div style={{ fontSize: 36, fontWeight: 700, color: "#0f1117" }}>Varuflow</div>
        </div>
        <div
          style={{
            marginTop: "auto",
            fontSize: title.length > 40 ? 56 : 72,
            fontWeight: 700,
            color: "#0f1117",
            lineHeight: 1.1,
            maxWidth: 1000,
          }}
        >
          {title}
        </div>
        <div style={{ marginTop: 24, fontSize: 30, color: "#6b7280", maxWidth: 960 }}>
          {subtitle}
        </div>
        <div style={{ marginTop: 48, width: 160, height: 10, background: "#2f5ea8" }} />
      </div>
    ),
    OG_SIZE,
  );
}
