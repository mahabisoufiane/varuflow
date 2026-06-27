"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api-client";
import { toast } from "sonner";
import { CheckCircle2, XCircle, QrCode, Search } from "lucide-react";

interface TodayBooking {
  id: string;
  customer_name: string;
  service: string;
  staff_name: string;
  start_time: string;
  end_time: string;
  status: "confirmed" | "checked_in" | "no_show" | "completed";
  qr_code_url: string | null;
}

export default function CheckInPage() {
  const t = useTranslations("bookings");
  const [bookings, setBookings] = useState<TodayBooking[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [qrModal, setQrModal] = useState<string | null>(null);

  async function fetchBookings() {
    try {
      const data = await api.get<TodayBooking[]>("/api/bookings/today");
      setBookings(data || []);
    } catch {
      toast.error(t("loadError"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchBookings();
  }, []);

  async function handleCheckIn(id: string) {
    try {
      await api.post(`/api/bookings/${id}/checkin`);
      toast.success(t("checkedIn"));
      fetchBookings();
    } catch {
      toast.error(t("checkinError"));
    }
  }

  async function handleNoShow(id: string) {
    try {
      await api.post(`/api/bookings/${id}/noshow`);
      toast.success(t("markedNoShow"));
      fetchBookings();
    } catch {
      toast.error(t("noShowError"));
    }
  }

  const filtered = bookings.filter((b) =>
    b.customer_name.toLowerCase().includes(search.toLowerCase())
  );

  const statusColors: Record<string, string> = {
    confirmed: "bg-blue-100 text-blue-800",
    checked_in: "bg-green-100 text-green-800",
    no_show: "bg-red-100 text-red-800",
    completed: "bg-gray-100 text-gray-800",
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-4 border-current border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="vf-text-1 text-2xl font-bold">{t("checkIn")}</h1>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 vf-text-m" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("searchCustomer")}
          className="w-full rounded-md border pl-10 pr-3 py-2 text-sm vf-border"
        />
      </div>

      {filtered.length === 0 ? (
        <p className="vf-text-m text-center py-12">{t("noBookingsToday")}</p>
      ) : (
        <div className="space-y-3">
          {filtered.map((booking) => (
            <div
              key={booking.id}
              className="vf-bg-card vf-border rounded-lg p-4 flex items-center justify-between"
            >
              <div className="space-y-1">
                <p className="vf-text-1 font-medium">{booking.customer_name}</p>
                <p className="vf-text-m text-sm">
                  {booking.service} &middot; {booking.staff_name}
                </p>
                <p className="vf-text-m text-sm">
                  {new Date(booking.start_time).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}{" "}
                  &ndash;{" "}
                  {new Date(booking.end_time).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </p>
                <span
                  className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                    statusColors[booking.status] || ""
                  }`}
                >
                  {booking.status.replace("_", " ")}
                </span>
              </div>

              <div className="flex items-center gap-2">
                {booking.qr_code_url && (
                  <button
                    onClick={() => setQrModal(booking.qr_code_url)}
                    className="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm hover:bg-accent vf-border"
                    title={t("showQr")}
                  >
                    <QrCode className="h-4 w-4" />
                  </button>
                )}
                {booking.status === "confirmed" && (
                  <>
                    <button
                      onClick={() => handleCheckIn(booking.id)}
                      className="inline-flex items-center gap-1 rounded-md bg-green-600 px-3 py-1.5 text-sm text-white hover:bg-green-700"
                    >
                      <CheckCircle2 className="h-4 w-4" />
                      {t("checkInBtn")}
                    </button>
                    <button
                      onClick={() => handleNoShow(booking.id)}
                      className="inline-flex items-center gap-1 rounded-md border border-red-300 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50"
                    >
                      <XCircle className="h-4 w-4" />
                      {t("noShow")}
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {qrModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setQrModal(null)}
        >
          <div
            className="vf-bg-card rounded-lg p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <img src={qrModal} alt="QR Code" className="h-64 w-64" />
            <button
              onClick={() => setQrModal(null)}
              className="mt-4 w-full rounded-md border px-3 py-2 text-sm vf-border hover:bg-accent"
            >
              {t("close")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
