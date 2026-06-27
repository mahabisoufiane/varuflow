"use client";

/**
 * BookingCalendar — minimal chronological list view.
 *
 * A real grid calendar lives on the roadmap; this MVP renders every
 * appointment in a single column sorted by start-time, with status
 * badges so ops can spot cancellations at a glance. Loading state is
 * handled via a skeleton row rather than a spinner because the list
 * is often small and the spinner would flash.
 */
import { cn } from "@/lib/utils";

interface Appointment {
  id: string;
  start_time: string;
  end_time: string;
  status: string;
  channel: string;
  notes: string | null;
}

const STATUS_STYLES: Record<string, string> = {
  booked: "bg-blue-100 text-blue-700",
  confirmed: "bg-emerald-100 text-emerald-700",
  completed: "bg-gray-100 text-gray-700",
  cancelled: "bg-rose-100 text-rose-700",
  no_show: "bg-amber-100 text-amber-700",
  waitlisted: "bg-violet-100 text-violet-700",
};

export default function BookingCalendar({
  appointments,
  loading,
}: {
  appointments: Appointment[];
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="space-y-2">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-16 animate-pulse rounded-xl bg-gray-100" />
        ))}
      </div>
    );
  }
  if (appointments.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-gray-300 p-8 text-center text-sm text-gray-500">
        No appointments yet.
      </div>
    );
  }
  return (
    <ul className="space-y-2">
      {appointments.map((a) => (
        <li
          key={a.id}
          className="flex items-center justify-between rounded-xl border border-gray-200 bg-white p-3"
        >
          <div>
            <div className="text-sm font-medium">
              {new Date(a.start_time).toLocaleString()}
            </div>
            <div className="text-xs text-gray-500">
              {a.channel} · ends {new Date(a.end_time).toLocaleTimeString()}
            </div>
          </div>
          <span
            className={cn(
              "rounded-full px-2 py-1 text-xs",
              STATUS_STYLES[a.status] ?? "bg-gray-100 text-gray-700",
            )}
          >
            {a.status}
          </span>
        </li>
      ))}
    </ul>
  );
}
