// frontend/src/app/api/og/route.tsx
// OG image generation using @vercel/og (Edge runtime).
// Route: /api/og?title=...&category=...

import { ImageResponse } from "next/og";
import type { NextRequest } from "next/server";

export const runtime = "edge";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const title = searchParams.get("title") ?? "Varuflow Blog";
  const category = searchParams.get("category") ?? "";

  return new ImageResponse(
    (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          width: "1200px",
          height: "630px",
          background: "linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%)",
          padding: "60px",
          fontFamily: "system-ui, sans-serif",
          position: "relative",
        }}
      >
        {/* Glow */}
        <div
          style={{
            position: "absolute",
            top: "-80px",
            left: "50%",
            transform: "translateX(-50%)",
            width: "800px",
            height: "400px",
            background: "radial-gradient(ellipse, rgba(37,99,235,0.3) 0%, transparent 70%)",
            pointerEvents: "none",
          }}
        />

        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "40px" }}>
          <div
            style={{
              display: "flex",
              width: "40px",
              height: "40px",
              borderRadius: "10px",
              background: "linear-gradient(135deg, #2563EB, #7C3AED)",
              alignItems: "center",
              justifyContent: "center",
              color: "white",
              fontWeight: "bold",
              fontSize: "18px",
            }}
          >
            V
          </div>
          <span style={{ fontSize: "22px", fontWeight: "bold", color: "white" }}>Varuflow</span>
        </div>

        {/* Category badge */}
        {category && (
          <div
            style={{
              display: "flex",
              marginBottom: "20px",
              padding: "6px 14px",
              borderRadius: "999px",
              border: "1px solid rgba(37,99,235,0.35)",
              background: "rgba(37,99,235,0.15)",
              color: "#a5b4fc",
              fontSize: "14px",
              fontWeight: "600",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              width: "fit-content",
            }}
          >
            {category}
          </div>
        )}

        {/* Title */}
        <div
          style={{
            fontSize: title.length > 60 ? "36px" : "48px",
            fontWeight: "800",
            color: "white",
            lineHeight: "1.2",
            maxWidth: "900px",
            flex: 1,
          }}
        >
          {title}
        </div>

        {/* Footer */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginTop: "40px",
            paddingTop: "24px",
            borderTop: "1px solid rgba(255,255,255,0.1)",
          }}
        >
          <span style={{ color: "#64748b", fontSize: "14px" }}>varuflow.com/blog</span>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 20px",
              background: "linear-gradient(135deg, #2563EB, #7C3AED)",
              borderRadius: "8px",
              color: "white",
              fontSize: "14px",
              fontWeight: "600",
            }}
          >
            Read article →
          </div>
        </div>
      </div>
    ),
    {
      width: 1200,
      height: 630,
    },
  );
}
