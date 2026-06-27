"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api-client";
import { toast } from "sonner";
import { UserPlus, Clock, ArrowRightLeft, Trash2 } from "lucide-react";

interface WalkIn {
  id: string;
  customer_name: string;
  party_size: number;
  service_requested: string | null;
  estimated_wait_minutes: number;
  status: string;
  created_at: string;
}

export default function WalkInsPage() {
  const t = useTranslations("bookings");
  const [queue, setQueue] = useState<WalkIn[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [name, setName] = useState("");
  const [partySize, setPartySize] = useState(1);
  const [service, setService] = useState("");

  async function fetchQueue() {
    try {
      const data = await api.get<WalkIn[]>("/api/bookings/waitlist");
      setQueue(data || []);
    } catch {
      toast.error(t("loadError"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchQueue();
  }, []);

  async function handleAdd() {
    if (!name.trim()) return;
    try {
      await api.post("/api/bookings/waitlist", {
        customer_name: name.trim(),
        party_size: partySize,
        service_requested: service || null,
      });
      toast.success(t("walkinAdded"));
      setName("");
      setPartySize(1);
      setService("");
      setShowAddForm(false);
      fetchQueue();
    } catch {
      toast.error(t("walkinAddError"));
    }
  }

  async function handleConvert(id: string) {
    try {
      await api.post(`/api/bookings/waitlist/${id}/convert`);
      toast.success(t("convertedToBooking"));
      fetchQueue();
    } catch {
      toast.error(t("convertError"));
    }
  }

  async function handleRemove(id: string) {
    try {
      await api.delete(`/api/bookings/waitlist/${id}`);
      toast.success(t("walkinRemoved"));
      fetchQueue();
    } catch {
      toast.error(t("removeError"));
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-4 border-current border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="vf-text-1 text-2xl font-bold">{t("walkIns")}</h1>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90"
        >
          <UserPlus className="h-4 w-4" />
          {t("addWalkIn")}
        </button>
      </div>

      {showAddForm && (
        <div className="vf-bg-card vf-border rounded-lg p-4 space-y-3">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("customerName")}
            className="w-full rounded-md border px-3 py-2 text-sm vf-border"
          />
          <div className="flex gap-3">
            <input
              type="number"
              min={1}
              value={partySize}
              onChange={(e) => setPartySize(Number(e.target.value))}
              placeholder={t("partySize")}
              className="w-24 rounded-md border px-3 py-2 text-sm vf-border"
            />
            <input
              value={service}
              onChange={(e) => setService(e.target.value)}
              placeholder={t("serviceRequested")}
              className="flex-1 rounded-md border px-3 py-2 text-sm vf-border"
            />
          </div>
          <button
            onClick={handleAdd}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90"
          >
            {t("confirm")}
          </button>
        </div>
      )}

      {queue.length === 0 ? (
        <p className="vf-text-m text-center py-12">{t("noWalkIns")}</p>
      ) : (
        <div className="space-y-3">
          {queue.map((item, idx) => (
            <div
              key={item.id}
              className="vf-bg-card vf-border rounded-lg p-4 flex items-center justify-between"
            >
              <div className="flex items-center gap-4">
                <span className="vf-text-m text-lg font-mono w-8 text-center">
                  #{idx + 1}
                </span>
                <div>
                  <p className="vf-text-1 font-medium">{item.customer_name}</p>
                  <div className="flex items-center gap-3 vf-text-m text-sm">
                    <span className="inline-flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      ~{item.estimated_wait_minutes} min
                    </span>
                    {item.service_requested && (
                      <span>{item.service_requested}</span>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleConvert(item.id)}
                  className="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm hover:bg-accent vf-border"
                  title={t("convertToBooking")}
                >
                  <ArrowRightLeft className="h-4 w-4" />
                  {t("convert")}
                </button>
                <button
                  onClick={() => handleRemove(item.id)}
                  className="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm text-destructive hover:bg-destructive/10 vf-border"
                  title={t("remove")}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
