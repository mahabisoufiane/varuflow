"use client";

import { ExternalLink, Monitor, Wifi, WifiOff } from "lucide-react";

const POS_URL = import.meta?.env?.VITE_POS_URL ?? "http://localhost:3002";

export default function PosRedirectPage() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center p-8">
      <div className="max-w-md w-full rounded-2xl border border-gray-200 bg-white p-8 shadow-sm text-center space-y-5">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-50">
          <Monitor className="h-7 w-7 text-emerald-600" />
        </div>

        <div>
          <h1 className="text-xl font-semibold text-gray-900">POS has moved</h1>
          <p className="mt-2 text-sm text-gray-500">
            The cash register is now a standalone app — optimized for tablets
            with offline support and faster load times.
          </p>
        </div>

        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-left space-y-2">
          <div className="flex items-center gap-2 text-xs font-medium text-emerald-700">
            <Wifi className="h-3.5 w-3.5" />
            Works offline
          </div>
          <div className="flex items-center gap-2 text-xs font-medium text-emerald-700">
            <Monitor className="h-3.5 w-3.5" />
            Installable on tablets (Add to Home Screen)
          </div>
        </div>

        <a
          href={process.env.NEXT_PUBLIC_POS_URL ?? "http://localhost:3002"}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-700 transition-colors"
        >
          Open POS App
          <ExternalLink className="h-4 w-4" />
        </a>

        <p className="text-xs text-gray-400">
          POS settings and reports remain available in Settings → POS Configuration.
        </p>
      </div>
    </div>
  );
}
