"use client";

import { ExternalLink, Monitor } from "lucide-react";

export default function ZReportRedirectPage() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center p-8">
      <div className="max-w-md w-full rounded-2xl border border-gray-200 bg-white p-8 shadow-sm text-center space-y-5">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-50">
          <Monitor className="h-7 w-7 text-emerald-600" />
        </div>

        <div>
          <h1 className="text-xl font-semibold text-gray-900">Z-Reports have moved</h1>
          <p className="mt-2 text-sm text-gray-500">
            Z-reports and session history are now part of the standalone POS app.
            Open the POS app and close a session to generate a Z-report.
          </p>
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
      </div>
    </div>
  );
}
