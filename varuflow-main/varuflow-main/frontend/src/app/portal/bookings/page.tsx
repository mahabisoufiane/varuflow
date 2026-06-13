"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { portalApi, PORTAL_TOKEN_KEY } from "@/lib/portal-client";
import { toast } from "sonner";
import { Calendar, X, RotateCcw } from "lucide-react";

interface Service { id: string; name: string; duration_minutes: number; price: number | null; }
interface Booking { id: string; service_id: string | null; start_time: string | null; end_time: string | null; status: string; }

const STATUS_STYLE: Record<string, string> = {
  completed: "bg-green-100 text-green-800",
  cancelled: "bg-red-100 text-red-800",
  booked: "bg-blue-100 text-blue-800",
  confirmed: "bg-indigo-100 text-indigo-800",
};

export default function PortalBookingsPage() {
  const router = useRouter();
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [showBook, setShowBook] = useState(false);
  const [form, setForm] = useState({ service_id: "", start_time: "" });
  const [rescheduleId, setRescheduleId] = useState<string | null>(null);
  const [newTime, setNewTime] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(PORTAL_TOKEN_KEY)) { router.replace("/portal/login"); return; }
    load();
    portalApi.get<Service[]>("/api/portal/services").then(setServices).catch(() => {});
  }, []);

  async function load() {
    try {
      const data = await portalApi.get<Booking[]>("/api/portal/bookings");
      setBookings(data);
    } catch {
      toast.error("Failed to load bookings");
    }
  }

  async function book() {
    if (!form.service_id || !form.start_time) return;
    setSubmitting(true);
    try {
      await portalApi.post("/api/portal/bookings", form);
      setShowBook(false);
      setForm({ service_id: "", start_time: "" });
      toast.success("Appointment booked");
      await load();
    } catch {
      toast.error("Booking failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function cancel(id: string) {
    if (!confirm("Cancel this appointment?")) return;
    try {
      await portalApi.post(`/api/portal/bookings/${id}/cancel`, {});
      toast.success("Appointment cancelled");
      await load();
    } catch (err: any) {
      toast.error(err?.detail || "Failed to cancel");
    }
  }

  async function reschedule() {
    if (!rescheduleId || !newTime) return;
    setSubmitting(true);
    try {
      await portalApi.patch(`/api/portal/bookings/${rescheduleId}/reschedule`, {
        new_start_time: new Date(newTime).toISOString(),
      });
      toast.success("Appointment rescheduled");
      setRescheduleId(null);
      setNewTime("");
      await load();
    } catch (err: any) {
      toast.error(err?.detail || "Failed to reschedule");
    } finally {
      setSubmitting(false);
    }
  }

  const canModify = (b: Booking) => !["cancelled", "completed", "no_show"].includes(b.status);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold flex items-center gap-2">
          <Calendar size={20} /> My Appointments
        </h1>
        <button onClick={() => setShowBook(true)} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">
          Book Appointment
        </button>
      </div>

      {/* New booking form */}
      {showBook && (
        <div className="bg-white border rounded-xl p-4 space-y-3 shadow-sm">
          <h2 className="font-semibold text-sm">New Appointment</h2>
          <select value={form.service_id} onChange={e => setForm({ ...form, service_id: e.target.value })}
            className="w-full border rounded-lg px-3 py-2 text-sm">
            <option value="">Select service…</option>
            {services.map(s => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.duration_minutes}min{s.price ? ` — ${s.price} SEK` : ""})
              </option>
            ))}
          </select>
          <input type="datetime-local" value={form.start_time}
            onChange={e => setForm({ ...form, start_time: e.target.value })}
            className="w-full border rounded-lg px-3 py-2 text-sm" />
          <div className="flex gap-2">
            <button onClick={book} disabled={submitting} className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm disabled:opacity-50">
              Confirm
            </button>
            <button onClick={() => setShowBook(false)} className="px-4 py-2 bg-gray-100 rounded-lg text-sm">Cancel</button>
          </div>
        </div>
      )}

      {/* Reschedule form */}
      {rescheduleId && (
        <div className="bg-white border border-indigo-200 rounded-xl p-4 space-y-3 shadow-sm">
          <h2 className="font-semibold text-sm">Reschedule Appointment</h2>
          <input type="datetime-local" value={newTime} onChange={e => setNewTime(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm" />
          <div className="flex gap-2">
            <button onClick={reschedule} disabled={submitting || !newTime}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm disabled:opacity-50">
              Confirm New Time
            </button>
            <button onClick={() => { setRescheduleId(null); setNewTime(""); }}
              className="px-4 py-2 bg-gray-100 rounded-lg text-sm">Cancel</button>
          </div>
        </div>
      )}

      {/* Bookings list */}
      <div className="space-y-2">
        {bookings.length === 0 && (
          <p className="text-center text-sm text-gray-500 py-8">No appointments yet.</p>
        )}
        {bookings.map(b => (
          <div key={b.id} className="bg-white border rounded-xl p-4 flex items-center justify-between">
            <div>
              <p className="font-medium text-sm">
                {b.start_time ? new Date(b.start_time).toLocaleString([], {
                  weekday: "short", month: "short", day: "numeric",
                  hour: "2-digit", minute: "2-digit",
                }) : "—"}
              </p>
              {b.end_time && (
                <p className="text-xs text-gray-400">
                  until {new Date(b.end_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2">
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLE[b.status] ?? "bg-gray-100 text-gray-600"}`}>
                {b.status}
              </span>
              {canModify(b) && (
                <>
                  <button onClick={() => { setRescheduleId(b.id); setNewTime(""); }}
                    title="Reschedule"
                    className="p-1.5 hover:bg-gray-100 rounded-lg text-indigo-600">
                    <RotateCcw size={14} />
                  </button>
                  <button onClick={() => cancel(b.id)} title="Cancel appointment"
                    className="p-1.5 hover:bg-red-50 rounded-lg text-red-500">
                    <X size={14} />
                  </button>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
