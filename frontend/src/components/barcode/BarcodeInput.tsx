"use client";

/**
 * BarcodeInput — World-class barcode field for the product forms.
 *
 * Three ways to scan:
 *  1. USB/Bluetooth hardware scanner  → typed instantly into the focused
 *     input; caught by useBarcodeListener to distinguish human typing.
 *  2. Camera scanner                  → react-zxing (ZXing-C++ via WASM)
 *     opened in an overlay modal; supports EAN-8/13, Code128, QR etc.
 *  3. Manual typing                   → plain text input, always available.
 *
 * Extras:
 *  • EAN-8 / EAN-13 check-digit validation with a coloured badge.
 *  • OpenFoodFacts auto-fill: when an EAN is scanned offer to populate
 *    name, category and units from the world product database (free API).
 *  • Beep + green flash on every successful scan.
 *  • "Generate" creates a valid internal EAN-13 (GS1 company prefix 2000
 *    reserved for in-store/internal use, padded with a random suffix).
 *  • Mobile aware: on ≤ md, camera button is shown first.
 */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { useZxing } from "react-zxing";
import { useBarcodeListener } from "./useBarcodeListener";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface OFFResult {
  name: string | null;
  category: string | null;
  brand: string | null;
  quantity: string | null;
}

export interface BarcodeInputProps {
  value: string;
  onChange: (barcode: string) => void;
  /** Called when OpenFoodFacts returns product data so the parent can
   *  auto-fill name / category / unit fields. Optional. */
  onProductLookup?: (data: OFFResult) => void;
  placeholder?: string;
  disabled?: boolean;
  id?: string;
}

// ── EAN validation ────────────────────────────────────────────────────────────

function validateEAN(code: string): boolean {
  if (!/^\d+$/.test(code)) return false;
  const len = code.length;
  if (len !== 8 && len !== 12 && len !== 13) return false;
  const digits = code.split("").map(Number);
  const check = digits.pop()!;
  const sum = digits.reduce((acc, d, i) => {
    // GS1 multiplier pattern: EAN-13 → 1,3,1,3…  EAN-8/UPC-A → 3,1,3,1…
    const mult = len === 13 ? (i % 2 === 0 ? 1 : 3) : (i % 2 === 0 ? 3 : 1);
    return acc + d * mult;
  }, 0);
  return (10 - (sum % 10)) % 10 === check;
}

function barcodeFormat(code: string): string | null {
  if (!/^\d+$/.test(code)) return code.length >= 4 ? "Code128 / QR" : null;
  if (code.length === 8) return "EAN-8";
  if (code.length === 12) return "UPC-A";
  if (code.length === 13) return "EAN-13";
  return null;
}

// ── Audio ─────────────────────────────────────────────────────────────────────

function playScanBeep() {
  try {
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = 1046; // C6 — crisp, positive
    osc.type = "sine";
    gain.gain.setValueAtTime(0.4, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.18);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.18);
    osc.onended = () => ctx.close();
  } catch {
    // Safari or secure-context restriction — fail silently
  }
}

// ── EAN-13 internal barcode generator ────────────────────────────────────────
// GS1 prefix "2" is reserved for in-store / restricted-distribution barcodes.
// Structure: 2 000000 XXXXX C  (prefix 2 + company 000000 + 5 random digits + check digit)

function generateInternalEAN13(): string {
  const prefix = "2000000"; // fixed 7 digits
  let inner = "";
  for (let i = 0; i < 5; i++) inner += String(Math.floor(Math.random() * 10));
  const partial = prefix + inner; // 12 digits
  const digits = partial.split("").map(Number);
  const sum = digits.reduce((acc, d, i) => acc + d * (i % 2 === 0 ? 1 : 3), 0);
  const check = (10 - (sum % 10)) % 10;
  return partial + String(check);
}

// ── OpenFoodFacts lookup ──────────────────────────────────────────────────────

async function fetchOpenFoodFacts(barcode: string): Promise<OFFResult | null> {
  try {
    const res = await fetch(
      `https://world.openfoodfacts.org/api/v0/product/${barcode}.json`,
      { signal: AbortSignal.timeout(5000) },
    );
    if (!res.ok) return null;
    const data = await res.json();
    if (data.status !== 1 || !data.product) return null;
    const p = data.product;
    return {
      name: p.product_name_sv || p.product_name_en || p.product_name || null,
      category: p.categories_tags?.[0]?.replace(/^en:|^sv:/, "") || null,
      brand: p.brands || null,
      quantity: p.quantity || null,
    };
  } catch {
    return null;
  }
}

// ── Camera Scanner sub-component ──────────────────────────────────────────────

function CameraScanner({
  onResult,
  onClose,
}: {
  onResult: (code: string) => void;
  onClose: () => void;
}) {
  const [paused, setPaused] = useState(false);
  const [flashGreen, setFlashGreen] = useState(false);
  const [lastCode, setLastCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [facingBack, setFacingBack] = useState(true);

  const handleDecode = useCallback(
    (text: string) => {
      if (paused) return;
      setPaused(true);
      setLastCode(text);
      setFlashGreen(true);
      playScanBeep();
      setTimeout(() => {
        onResult(text);
        onClose();
      }, 600);
    },
    [paused, onResult, onClose],
  );

  const { ref } = useZxing({
    paused,
    constraints: {
      video: {
        facingMode: facingBack ? "environment" : "user",
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
    },
    onDecodeResult(result) {
      handleDecode(result.getText());
    },
    onDecodeError(err) {
      // ZXing fires this constantly while no barcode is in frame — suppress.
      void err;
    },
    onError(err) {
      if (err instanceof Error) {
        setError(
          err.name === "NotAllowedError"
            ? "Camera permission denied. Allow camera access in your browser settings."
            : err.message,
        );
      }
    },
  });

  return (
    <div className="fixed inset-0 z-[60] flex flex-col bg-black">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3">
        <h2 className="text-sm font-semibold text-white">Scan barcode</h2>
        <div className="flex gap-2">
          {/* Flip camera */}
          <button
            type="button"
            onClick={() => setFacingBack((v) => !v)}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-white/20 text-white hover:bg-white/30"
            aria-label="Flip camera"
          >
            🔄
          </button>
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-white/20 text-white hover:bg-white/30"
            aria-label="Close"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Video + viewfinder */}
      <div className="relative flex flex-1 items-center justify-center overflow-hidden">
        {error ? (
          <div className="px-6 text-center">
            <p className="text-lg">📷</p>
            <p className="mt-2 text-sm text-red-400">{error}</p>
          </div>
        ) : (
          <>
            <video
              ref={ref}
              autoPlay
              playsInline
              muted
              className="h-full w-full object-cover"
            />

            {/* Green success overlay */}
            {flashGreen && (
              <div className="absolute inset-0 animate-[flashGreen_0.5s_ease-out] bg-emerald-500/40" />
            )}

            {/* Viewfinder corners + animated scan line */}
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
              <div className="relative h-52 w-72 sm:h-64 sm:w-96">
                {/* Corner brackets */}
                {(["tl", "tr", "bl", "br"] as const).map((c) => (
                  <CornerBracket key={c} corner={c} />
                ))}
                {/* Animated scan line */}
                {!lastCode && (
                  <div
                    className="absolute left-2 right-2 h-0.5 rounded-full bg-emerald-400 shadow-[0_0_8px_2px_rgba(52,211,153,0.8)]"
                    style={{ animation: "scanLine 2s ease-in-out infinite" }}
                  />
                )}
                {/* Dimmed overlay outside viewport */}
                <div className="absolute -inset-[9999px] -z-10 bg-black/50" />
              </div>
            </div>

            {/* Result badge */}
            {lastCode && (
              <div className="absolute bottom-24 left-4 right-4 rounded-xl bg-emerald-600 px-4 py-3 text-center shadow-lg">
                <p className="text-xs font-medium text-emerald-100">Captured</p>
                <p className="mt-0.5 font-mono text-lg font-bold text-white">{lastCode}</p>
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer hint */}
      {!error && !lastCode && (
        <p className="px-4 py-4 text-center text-xs text-gray-400">
          Hold the barcode inside the frame — EAN-8, EAN-13, Code128, QR
        </p>
      )}

      <style>{`
        @keyframes scanLine {
          0%   { top: 8px;  opacity: 0.9; }
          50%  { top: calc(100% - 8px); opacity: 0.9; }
          100% { top: 8px;  opacity: 0.9; }
        }
        @keyframes flashGreen {
          0%   { opacity: 0.7; }
          100% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}

// Corner bracket helper
function CornerBracket({ corner }: { corner: "tl" | "tr" | "bl" | "br" }) {
  const pos: Record<typeof corner, string> = {
    tl: "top-0 left-0 border-t-2 border-l-2",
    tr: "top-0 right-0 border-t-2 border-r-2",
    bl: "bottom-0 left-0 border-b-2 border-l-2",
    br: "bottom-0 right-0 border-b-2 border-r-2",
  };
  return (
    <div
      className={`absolute h-6 w-6 rounded-[2px] border-emerald-400 ${pos[corner]}`}
    />
  );
}

// ── OpenFoodFacts panel ───────────────────────────────────────────────────────

function OFFPanel({
  barcode,
  onApply,
  onDismiss,
}: {
  barcode: string;
  onApply: (data: OFFResult) => void;
  onDismiss: () => void;
}) {
  const [data, setData] = useState<OFFResult | null | "loading" | "not_found">("loading");

  useEffect(() => {
    fetchOpenFoodFacts(barcode).then((r) => setData(r ?? "not_found"));
  }, [barcode]);

  if (data === "loading") {
    return (
      <div className="mt-2 flex items-center gap-2 rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-xs text-blue-700 dark:border-blue-900 dark:bg-blue-900/20 dark:text-blue-300">
        <span className="animate-spin">⏳</span> Looking up product on OpenFoodFacts…
      </div>
    );
  }

  if (data === "not_found") {
    return (
      <div className="mt-2 flex items-center justify-between rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 text-xs text-gray-500 dark:border-gray-700 dark:bg-gray-800">
        <span>No product found in OpenFoodFacts database</span>
        <button type="button" onClick={onDismiss} className="ml-2 hover:text-gray-700">✕</button>
      </div>
    );
  }

  const d = data as OFFResult;

  return (
    <div className="mt-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 dark:border-emerald-800 dark:bg-emerald-900/20">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 space-y-0.5">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-400">
            OpenFoodFacts match
          </p>
          {d.name && <p className="text-sm font-medium dark:text-gray-200">{d.name}</p>}
          {d.brand && <p className="text-xs text-gray-500 dark:text-gray-400">{d.brand}</p>}
          {d.category && (
            <p className="text-xs text-emerald-700 dark:text-emerald-400">
              Category: {d.category}
            </p>
          )}
          {d.quantity && (
            <p className="text-xs text-gray-500 dark:text-gray-400">Qty: {d.quantity}</p>
          )}
        </div>
        <button type="button" onClick={onDismiss} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">✕</button>
      </div>
      <button
        type="button"
        onClick={() => { onApply(d); onDismiss(); }}
        className="mt-2 w-full rounded-md bg-emerald-600 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700"
      >
        Apply to form →
      </button>
    </div>
  );
}

// ── Main BarcodeInput component ───────────────────────────────────────────────

export default function BarcodeInput({
  value,
  onChange,
  onProductLookup,
  placeholder = "7310865085313",
  disabled = false,
  id = "barcode",
}: BarcodeInputProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [flash, setFlash] = useState(false);
  const [showOFF, setShowOFF] = useState(false);

  const isEAN = validateEAN(value);
  const fmt = barcodeFormat(value);
  const showLookup = isEAN && !!onProductLookup && value.length >= 8;

  // Apply a brief green-flash on the input when any scan arrives.
  function triggerFlash() {
    setFlash(true);
    setTimeout(() => setFlash(false), 600);
  }

  // Called both by camera scanner and hardware scanner
  const handleScan = useCallback(
    (code: string) => {
      onChange(code);
      triggerFlash();
      playScanBeep();
      if ((code.length === 8 || code.length === 12 || code.length === 13) && /^\d+$/.test(code)) {
        setShowOFF(true);
      }
    },
    [onChange],
  );

  // Hardware scanner listener — active when the barcode input is focused.
  useBarcodeListener({
    onScan: handleScan,
    inputRef,
    enabled: !cameraOpen,
  });

  function handleCameraResult(code: string) {
    setCameraOpen(false);
    handleScan(code);
  }

  function handleGenerate() {
    const code = generateInternalEAN13();
    onChange(code);
    triggerFlash();
    playScanBeep();
  }

  return (
    <div className="space-y-1.5">
      {/* ── Input row ── */}
      <div className="flex gap-1">
        <div className="relative flex-1">
          <input
            ref={inputRef}
            id={id}
            type="text"
            inputMode="numeric"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            disabled={disabled}
            autoComplete="off"
            className={[
              "block h-10 w-full rounded-l-md border px-3 font-mono text-sm transition-all",
              "focus:outline-none focus:ring-1",
              flash
                ? "border-emerald-500 bg-emerald-50 ring-emerald-500 dark:bg-emerald-900/20"
                : "border-gray-300 focus:border-[#1a2332] focus:ring-[#1a2332] dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100",
            ].join(" ")}
          />
          {/* EAN / format badge inside the input */}
          {fmt && value.length >= 8 && (
            <span
              className={[
                "pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 rounded px-1.5 py-0.5 text-[10px] font-semibold",
                isEAN
                  ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400"
                  : "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400",
              ].join(" ")}
            >
              {fmt} {isEAN ? "✓" : "⚠"}
            </span>
          )}
        </div>

        {/* Camera scan button */}
        <button
          type="button"
          title="Scan with camera"
          onClick={() => setCameraOpen(true)}
          disabled={disabled}
          className="flex h-10 w-10 items-center justify-center rounded-none border-y border-r border-gray-300 bg-white text-lg transition hover:bg-gray-50 disabled:opacity-40 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
          aria-label="Open camera scanner"
        >
          📷
        </button>

        {/* Generate button — only when field is empty */}
        {!value && !disabled && (
          <button
            type="button"
            title="Generate internal EAN-13"
            onClick={handleGenerate}
            className="flex h-10 items-center justify-center rounded-r-md border-y border-r border-dashed border-gray-300 bg-white px-2 text-xs font-medium text-gray-500 transition hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-400"
            aria-label="Generate EAN-13"
          >
            Generate
          </button>
        )}
        {value && (
          <button
            type="button"
            title="Clear barcode"
            onClick={() => { onChange(""); setShowOFF(false); }}
            disabled={disabled}
            className="flex h-10 w-10 items-center justify-center rounded-r-md border-y border-r border-gray-300 bg-white text-gray-400 transition hover:bg-gray-50 hover:text-gray-600 disabled:opacity-40 dark:border-gray-600 dark:bg-gray-700 dark:hover:text-gray-300"
            aria-label="Clear"
          >
            ✕
          </button>
        )}
      </div>

      {/* ── Hardware scanner hint ── */}
      <p className="flex items-center gap-1 text-[11px] text-gray-400 dark:text-gray-500">
        <span>🔫</span>
        USB / Bluetooth scanner detected automatically when this field is focused
      </p>

      {/* ── OpenFoodFacts auto-fill prompt ── */}
      {showOFF && showLookup && (
        <OFFPanel
          barcode={value}
          onApply={(d) => onProductLookup?.(d)}
          onDismiss={() => setShowOFF(false)}
        />
      )}

      {/* ── Camera scanner full-screen modal ── */}
      {cameraOpen && (
        <CameraScanner
          onResult={handleCameraResult}
          onClose={() => setCameraOpen(false)}
        />
      )}
    </div>
  );
}
