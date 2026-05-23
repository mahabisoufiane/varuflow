"use client";

/**
 * Bookings page — salon & spa calendar.
 *
 * MVP surface (Item 31). Lists today's appointments in chronological
 * order and exposes the "New appointment" + "Walk-in" + "Waitlist"
 * actions. The calendar grid and drag-to-reschedule interaction live
 * in ``@/components/bookings/BookingCalendar`` and are iterated on in
 * follow-up items once the MENA pilot tenants confirm the slot
 * computation feels right.
 *
 * Everything here is client-side — the page renders a skeleton, then
 * fetches ``/api/bookings/appointments`` via the shared api-client. No
 * SSR cache because the calendar is inherently per-user state that
 * ops-team members expect to refresh on focus.
 */
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api-client";
import { toast } from "sonner";
import { CalendarDays, UserPlus, Users, Clock } from "lucide-react";
import BookingCalendar from "@/components/bookings/BookingCalendar";
import SlotPicker from "@/components/bookings/SlotPicker";

interface Appointment {
  id: string;
  service_id: string;
  staff_id: string;
  start_time: string;
  end_time: string;
  status: string;
  channel: string;
  notes: string | null;
  loyalty_points_awarded: number;
}

export default function BookingsPage() {
  const t = useTranslations("bookings");
  const [appts, setAppts] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const data = await api.get<Appointment[]>("/api/bookings/appointments");
        setAppts(data || []);
      } catch (err) {
        toast.error(t("loadError"));
      } finally {
        setLoading(false);
      }
    })();
  }, [t]);

  return (
    <div className="flex flex-col gap-6 p-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <CalendarDays className="h-6 w-6" />
            {t("title")}
          </h1>
          <p className="text-sm text-gray-500">{t("subtitle")}</p>
        </div>
        <div className="flex gap-2">
          <button className="flex items-center gap-2 rounded-xl border px-3 py-2 text-sm">
            <UserPlus className="h-4 w-4" /> {t("newAppointment")}
          </button>
          <button className="flex items-center gap-2 rounded-xl border px-3 py-2 text-sm">
            <Users className="h-4 w-4" /> {t("walkIn")}
          </button>
        </div>
      </header>

      <BookingCalendar appointments={appts} loading={loading} />

      <section className="rounded-2xl border border-gray-200 bg-white p-4">
        <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
          <Clock className="h-4 w-4" /> {t("availableSlots")}
        </h2>
        <SlotPicker />
      </section>
    </div>
  );
}
