"use client";

import { useEffect, useRef } from "react";
import { useZxing } from "react-zxing";
import { X } from "lucide-react";

interface Props {
  onResult: (code: string) => void;
  onClose: () => void;
}

export default function BarcodeScanner({ onResult, onClose }: Props) {
  const lastCode = useRef<string>("");
  const lastTime = useRef<number>(0);

  const { ref } = useZxing({
    onDecodeResult(result) {
      const code = result.getText();
      const now = Date.now();
      // Debounce: ignore same code within 2 seconds
      if (code === lastCode.current && now - lastTime.current < 2000) return;
      lastCode.current = code;
      lastTime.current = now;
      onResult(code);
    },
    constraints: { video: { facingMode: "environment" } },
  });

  // Close on Escape
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/80" onClick={onClose} />
      <div className="relative w-full max-w-sm mx-4">
        <div className="relative overflow-hidden rounded-2xl bg-black shadow-2xl">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 bg-black/60 backdrop-blur-sm">
            <p className="text-sm font-medium text-white">Point camera at barcode</p>
            <button onClick={onClose} className="rounded-full p-1.5 text-white/70 hover:bg-white/10 transition-colors">
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Camera feed */}
          <div className="relative aspect-[4/3]">
            <video ref={ref as React.RefObject<HTMLVideoElement>} className="w-full h-full object-cover" />

            {/* Scanning overlay */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              {/* Corner guides */}
              <div className="relative w-56 h-32">
                {[
                  "top-0 left-0 border-t-2 border-l-2 rounded-tl",
                  "top-0 right-0 border-t-2 border-r-2 rounded-tr",
                  "bottom-0 left-0 border-b-2 border-l-2 rounded-bl",
                  "bottom-0 right-0 border-b-2 border-r-2 rounded-br",
                ].map((cls, i) => (
                  <div key={i} className={`absolute w-5 h-5 border-white ${cls}`} />
                ))}
                {/* Scan line animation */}
                <div className="absolute inset-x-0 h-0.5 bg-green-400/80 animate-scan" />
              </div>
            </div>
          </div>

          <p className="px-4 py-3 text-center text-xs text-white/50 bg-black">
            ESC to close · tap background to dismiss
          </p>
        </div>
      </div>

      <style>{`
        @keyframes scan {
          0%, 100% { top: 10%; }
          50% { top: 85%; }
        }
        .animate-scan { animation: scan 2s ease-in-out infinite; position: absolute; }
      `}</style>
    </div>
  );
}
