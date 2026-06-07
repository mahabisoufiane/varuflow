import { useState } from "react";
import { loginWithPin } from "../lib/auth";
import { toast } from "sonner";

export default function PinLogin({ onSuccess }: { onSuccess: () => void }) {
  const [pin, setPin] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (pin.length < 4) { toast.error("PIN must be at least 4 digits"); return; }
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
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-50 dark:bg-gray-900 p-4">
      <div className="w-full max-w-xs rounded-2xl bg-white dark:bg-gray-800 p-8 shadow-xl text-center">
        <div className="mb-6">
          <div className="mx-auto h-14 w-14 rounded-2xl bg-emerald-600 flex items-center justify-center text-white text-2xl font-bold mb-3">V</div>
          <h1 className="text-2xl font-bold dark:text-white">Varuflow POS</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Enter your PIN to start</p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="mb-4 flex justify-center gap-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className={`h-3 w-3 rounded-full transition ${
                  i < pin.length ? "bg-emerald-600" : "bg-gray-200 dark:bg-gray-600"
                }`}
              />
            ))}
          </div>

          <div className="mb-4 grid grid-cols-3 gap-3">
            {["1","2","3","4","5","6","7","8","9","","0","⌫"].map((d) => (
              <button
                key={d}
                type={d === "" ? "button" : "button"}
                disabled={d === ""}
                onClick={() => {
                  if (d === "⌫") setPin((p) => p.slice(0, -1));
                  else if (d) handlePad(d);
                }}
                className={`h-14 rounded-xl text-xl font-semibold transition active:scale-95 ${
                  d === ""
                    ? "invisible"
                    : d === "⌫"
                    ? "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300"
                    : "bg-gray-100 text-gray-800 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-100"
                }`}
              >
                {d}
              </button>
            ))}
          </div>

          <button
            type="submit"
            disabled={pin.length < 4 || loading}
            className="h-12 w-full rounded-xl bg-emerald-600 text-base font-semibold text-white disabled:opacity-50 transition hover:bg-emerald-700"
          >
            {loading ? "…" : "Unlock"}
          </button>
        </form>
      </div>
    </div>
  );
}
