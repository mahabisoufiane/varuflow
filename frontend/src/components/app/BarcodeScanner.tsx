"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useZxing } from "react-zxing";
import { X, Loader2, AlertCircle } from "lucide-react";

interface Props {
  onResult: (code: string) => void;
  onClose: () => void;
}

// Native BarcodeDetector API (Chrome 88+, Edge, Android WebView) — much faster
// and more accurate than the WASM-based ZXing fallback.
declare global {
  interface Window {
    BarcodeDetector?: typeof NativeBarcodeDetector;
  }
}
declare class NativeBarcodeDetector {
  constructor(options?: { formats?: string[] });
  detect(image: ImageBitmapSource | HTMLVideoElement): Promise<Array<{ rawValue: string; format: string }>>;
  static getSupportedFormats(): Promise<string[]>;
}

// ── Native-API scanner ────────────────────────────────────────────────────────

function NativeScanner({ onResult, onClose }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef = useRef<number>(0);
  const lastCode = useRef("");
  const lastTime = useRef(0);
  const [status, setStatus] = useState<"loading" | "scanning" | "error">("loading");
  const [errorMsg, setErrorMsg] = useState("");

  const emit = useCallback((code: string) => {
    const now = Date.now();
    if (code === lastCode.current && now - lastTime.current < 2000) return;
    lastCode.current = code;
    lastTime.current = now;
    onResult(code);
  }, [onResult]);

  useEffect(() => {
    let active = true;

    async function start() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
        });
        if (!active) { stream.getTracks().forEach(t => t.stop()); return; }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }
        setStatus("scanning");

        const formats = await window.BarcodeDetector!.getSupportedFormats();
        const detector = new window.BarcodeDetector!({ formats });

        function tick() {
          if (!active || !videoRef.current) return;
          detector.detect(videoRef.current)
            .then(results => { if (results[0]) emit(results[0].rawValue); })
            .catch(() => {})
            .finally(() => { rafRef.current = requestAnimationFrame(tick); });
        }
        rafRef.current = requestAnimationFrame(tick);
      } catch (err: any) {
        if (!active) return;
        setStatus("error");
        setErrorMsg(
          err.name === "NotAllowedError"
            ? "Camera permission denied. Allow camera access and try again."
            : `Camera error: ${err.message}`
        );
      }
    }
    start();

    return () => {
      active = false;
      cancelAnimationFrame(rafRef.current);
      streamRef.current?.getTracks().forEach(t => t.stop());
    };
  }, [emit]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return <ScannerShell videoRef={videoRef} status={status} errorMsg={errorMsg} onClose={onClose} />;
}

// ── ZXing fallback scanner ────────────────────────────────────────────────────

function ZxingScanner({ onResult, onClose }: Props) {
  const lastCode = useRef("");
  const lastTime = useRef(0);

  const { ref } = useZxing({
    onDecodeResult(result) {
      const code = result.getText();
      const now = Date.now();
      if (code === lastCode.current && now - lastTime.current < 2000) return;
      lastCode.current = code;
      lastTime.current = now;
      onResult(code);
    },
    constraints: { video: { facingMode: "environment", width: { ideal: 1280 } } },
    timeBetweenDecodingAttempts: 200,
  });

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <ScannerShell
      videoRef={ref as React.RefObject<HTMLVideoElement>}
      status="scanning"
      errorMsg=""
      onClose={onClose}
    />
  );
}

// ── Shared UI shell ───────────────────────────────────────────────────────────

function ScannerShell({
  videoRef,
  status,
  errorMsg,
  onClose,
}: {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  status: "loading" | "scanning" | "error";
  errorMsg: string;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/80" onClick={onClose} />
      <div className="relative w-full max-w-sm mx-4">
        <div className="relative overflow-hidden rounded-2xl bg-black shadow-2xl">
          <div className="flex items-center justify-between px-4 py-3 bg-black/60 backdrop-blur-sm">
            <p className="text-sm font-medium text-white">Point camera at barcode</p>
            <button onClick={onClose} className="rounded-full p-1.5 text-white/70 hover:bg-white/10 transition-colors">
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="relative aspect-[4/3] bg-black">
            {status === "loading" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-white/60">
                <Loader2 className="h-8 w-8 animate-spin" />
                <p className="text-xs">Starting camera…</p>
              </div>
            )}
            {status === "error" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-6 text-center">
                <AlertCircle className="h-8 w-8 text-red-400" />
                <p className="text-sm text-red-300">{errorMsg}</p>
                <button onClick={onClose} className="rounded-lg bg-white/10 px-4 py-2 text-xs text-white hover:bg-white/20">
                  Close
                </button>
              </div>
            )}

            <video
              ref={videoRef}
              className="w-full h-full object-cover"
              playsInline
              muted
            />

            {status === "scanning" && (
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="relative w-56 h-32">
                  {[
                    "top-0 left-0 border-t-2 border-l-2 rounded-tl",
                    "top-0 right-0 border-t-2 border-r-2 rounded-tr",
                    "bottom-0 left-0 border-b-2 border-l-2 rounded-bl",
                    "bottom-0 right-0 border-b-2 border-r-2 rounded-br",
                  ].map((cls, i) => (
                    <div key={i} className={`absolute w-5 h-5 border-white ${cls}`} />
                  ))}
                  <div className="absolute inset-x-0 h-0.5 bg-green-400/80 animate-scan" />
                </div>
              </div>
            )}
          </div>

          <p className="px-4 py-3 text-center text-xs text-white/50 bg-black">
            ESC or tap background to close
          </p>
        </div>
      </div>

      <style>{`
        @keyframes scan { 0%, 100% { top: 10%; } 50% { top: 85%; } }
        .animate-scan { animation: scan 2s ease-in-out infinite; position: absolute; }
      `}</style>
    </div>
  );
}

// ── Export: pick best available implementation ────────────────────────────────

export default function BarcodeScanner(props: Props) {
  // BarcodeDetector API is native (no WASM), faster, more accurate
  if (typeof window !== "undefined" && window.BarcodeDetector) {
    return <NativeScanner {...props} />;
  }
  // Fallback to ZXing (works in Firefox/Safari)
  return <ZxingScanner {...props} />;
}
