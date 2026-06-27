"use client";

/**
 * Shared camera viewfinder overlay: four corner brackets + animated scan line.
 * Rendered as an absolute overlay inside a relative-positioned camera container.
 *
 * Usage:
 *   <div className="relative aspect-video bg-black">
 *     <video ... />
 *     <ScannerViewfinder scanning={status === "scanning"} innerClassName="w-56 h-32" />
 *   </div>
 *
 * Canonical source — POS BarcodeScanner draws its own equivalent overlay and
 * points here in a comment.
 */

const CORNERS = [
  "top-0 left-0 border-t-2 border-l-2",
  "top-0 right-0 border-t-2 border-r-2",
  "bottom-0 left-0 border-b-2 border-l-2",
  "bottom-0 right-0 border-b-2 border-r-2",
] as const;

interface Props {
  /** Show/hide the viewfinder (e.g. hide after a successful scan). Default true. */
  scanning?: boolean;
  /** CSS color for brackets and scan line. Default emerald-400 (#34d399). */
  color?: string;
  /** Tailwind size classes for the inner target box. Default "w-56 h-32". */
  innerClassName?: string;
}

export function ScannerViewfinder({
  scanning = true,
  color = "#34d399",
  innerClassName = "w-56 h-32",
}: Props) {
  if (!scanning) return null;

  return (
    <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
      <div className={`relative ${innerClassName}`}>
        {CORNERS.map((cls, i) => (
          <div
            key={i}
            className={`absolute h-6 w-6 ${cls}`}
            style={{ borderColor: color }}
          />
        ))}
        <div
          className="absolute inset-x-0 h-0.5 rounded-full"
          style={{
            backgroundColor: color,
            boxShadow: `0 0 8px 2px ${color}80`,
            animation: "svfScan 2s ease-in-out infinite",
          }}
        />
      </div>
      <style>{`
        @keyframes svfScan {
          0%, 100% { top: 8px; }
          50%       { top: calc(100% - 8px); }
        }
      `}</style>
    </div>
  );
}
