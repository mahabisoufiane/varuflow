import { useState } from "react";
import { loginWithPin } from "../lib/auth";
import { toast } from "sonner";

export default function PinLogin({ onSuccess }: { onSuccess: () => void }) {
  const [pin, setPin] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (pin.length < 6) { toast.error("PIN must be 6 digits"); return; }
    setLoading(true);
    try {
      await loginWithPin(pin);
      onSuccess();
    } catch (err) {
      toast.error((err as Error).message);
      setPin("");
    } finally {
      setLoading(false);
    }
  }

  function handlePad(digit: string) {
    if (pin.length < 6) setPin((p) => p + digit);
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-900 p-4">
      {/* Logo */}
      <div className="mb-8 text-center">
        <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-500 shadow-lg shadow-emerald-500/30">
          <span className="text-3xl font-black text-white">V</span>
        </div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Varuflow POS</h1>
        <p className="mt-1 text-sm text-slate-400">Enter your PIN to continue</p>
      </div>

      <form onSubmit={handleSubmit} className="w-full max-w-[280px]">
        {/* PIN dots */}
        <div className="mb-6 flex justify-center gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className={`h-4 w-4 rounded-full transition-all duration-150 ${
                i < pin.length
                  ? "bg-emerald-400 scale-110 shadow-lg shadow-emerald-400/50"
                  : "bg-slate-700"
              }`}
            />
          ))}
        </div>

        {/* Numpad */}
        <div className="grid grid-cols-3 gap-3 mb-4">
          {["1","2","3","4","5","6","7","8","9","","0","⌫"].map((d, i) => (
            <button
              key={i}
              type="button"
              disabled={d === ""}
              onClick={() => {
                if (d === "⌫") setPin((p) => p.slice(0, -1));
                else if (d) handlePad(d);
              }}
              className={`h-16 rounded-2xl text-xl font-semibold transition active:scale-95 select-none ${
                d === ""
                  ? "invisible"
                  : d === "⌫"
                  ? "bg-slate-700 text-slate-300 hover:bg-slate-600 active:bg-slate-500"
                  : "bg-slate-700 text-white hover:bg-slate-600 active:bg-emerald-600"
              }`}
            >
              {d}
            </button>
          ))}
        </div>

        <button
          type="submit"
          disabled={pin.length < 6 || loading}
          className="h-14 w-full rounded-2xl bg-emerald-500 text-base font-bold text-white shadow-lg shadow-emerald-500/30 transition hover:bg-emerald-400 active:scale-[0.98] disabled:opacity-30 disabled:cursor-not-allowed"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              Verifying…
            </span>
          ) : "Unlock"}
        </button>
      </form>
    </div>
  );
}
