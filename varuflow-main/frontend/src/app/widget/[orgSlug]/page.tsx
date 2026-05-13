"use client";

/**
 * Public booking widget (Item 46).
 *
 * Embeddable, unauthenticated booking flow hosted at
 * ``/widget/<orgSlug>``. Salons paste the iframe snippet (returned by
 * ``GET /api/bookings/widget-embed``) onto their own site and this
 * page runs inside that iframe.
 *
 * The widget deliberately sidesteps the app-wide locale router (which
 * lives under ``/[locale]/(app)``) because public customers may land
 * here from any domain and have no Varuflow session. Arabic / Hebrew
 * RTL layout is driven by ``meta.rtl`` on the org record.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

// Resolve the API base at runtime. NEXT_PUBLIC_API_URL is injected by
// the Next.js build; fall back to same-origin in dev.
const API_BASE =
  (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_API_URL) ||
  (typeof window !== "undefined" ? window.location.origin : "");


interface OrgMeta {
  slug: string;
  name: string;
  brand_color: string;
  rtl: boolean;
}

interface ServiceRow {
  id: string;
  name: string;
  duration_minutes: number;
  price: number;
  category: string | null;
  description: string | null;
}

interface StaffRow {
  id: string;
  name: string;
  role: string | null;
  specialties: string[] | null;
}

interface SlotRow {
  start: string;
  end: string;
}


async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!r.ok) {
    const detail = await r.text().catch(() => "");
    throw new Error(detail || `${r.status}`);
  }
  if (r.status === 204) return undefined as T;
  return (await r.json()) as T;
}


export default function BookingWidget({
  params,
}: {
  params: { orgSlug: string };
}) {
  const slug = params.orgSlug;
  const [meta, setMeta] = useState<OrgMeta | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [services, setServices] = useState<ServiceRow[]>([]);
  const [staff, setStaff] = useState<StaffRow[]>([]);
  const [slots, setSlots] = useState<SlotRow[]>([]);
  const [step, setStep] = useState<1 | 2 | 3 | 4 | 5>(1);

  const [selectedService, setSelectedService] = useState<ServiceRow | null>(null);
  const [selectedStaff, setSelectedStaff] = useState<StaffRow | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<SlotRow | null>(null);
  const [day, setDay] = useState<string>(
    () => new Date().toISOString().slice(0, 10),
  );

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState<any>(null);

  // Load org meta + services + staff in parallel once the slug is known.
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const m = await api<OrgMeta>(`/api/widget/${slug}`);
        if (!active) return;
        setMeta(m);
        const [svcs, people] = await Promise.all([
          api<ServiceRow[]>(`/api/widget/${slug}/services`),
          api<StaffRow[]>(`/api/widget/${slug}/staff`),
        ]);
        if (!active) return;
        setServices(svcs);
        setStaff(people);
      } catch {
        if (active) setNotFound(true);
      }
    })();
    return () => { active = false; };
  }, [slug]);

  // Load slots when the (service, staff, day) tuple is complete.
  useEffect(() => {
    if (!selectedService || !selectedStaff || !day) return;
    let active = true;
    (async () => {
      try {
        const dayIso = new Date(`${day}T00:00:00Z`).toISOString();
        const data = await api<SlotRow[]>(
          `/api/widget/${slug}/slots?service_id=${selectedService.id}`
          + `&staff_id=${selectedStaff.id}`
          + `&day=${encodeURIComponent(dayIso)}`,
        );
        if (active) setSlots(data);
      } catch {
        if (active) setSlots([]);
      }
    })();
    return () => { active = false; };
  }, [slug, selectedService, selectedStaff, day]);

  const book = useCallback(async () => {
    if (!selectedService || !selectedStaff || !selectedSlot) return;
    setSubmitting(true);
    setError(null);
    try {
      const out = await api<any>(`/api/widget/${slug}/book`, {
        method: "POST",
        body: JSON.stringify({
          service_id: selectedService.id,
          staff_id: selectedStaff.id,
          start_time: selectedSlot.start,
          customer_name: name,
          customer_email: email,
          customer_phone: phone || null,
          notes: notes || null,
        }),
      });
      setConfirmed(out);
      setStep(5);
    } catch (e: any) {
      setError(e?.message || "Booking failed");
    } finally {
      setSubmitting(false);
    }
  }, [slug, selectedService, selectedStaff, selectedSlot, name, email, phone, notes]);

  const brand = meta?.brand_color || "#1a2332";
  const dir = meta?.rtl ? "rtl" : "ltr";

  if (notFound) {
    return (
      <div style={{ padding: 24, fontFamily: "sans-serif" }}>
        <h2>Salon not found</h2>
        <p>The booking widget could not load. Please check the link.</p>
      </div>
    );
  }

  if (!meta) {
    return (
      <div style={{ padding: 24, fontFamily: "sans-serif" }}>Loading…</div>
    );
  }

  return (
    <div
      dir={dir}
      className="w-full max-w-3xl mx-auto p-4 font-sans"
      style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}
    >
      {/* Header with brand color band */}
      <div
        className="w-full rounded-t-lg p-5 text-white"
        style={{ background: brand }}
      >
        <h1 className="text-xl font-semibold m-0">{meta.name}</h1>
        <p className="text-sm opacity-90 m-0 mt-1">Book your appointment</p>
      </div>

      <div className="border border-t-0 rounded-b-lg p-4 md:p-6 space-y-6">
        {/* Stepper */}
        <div className="flex gap-2 text-xs text-gray-600 flex-wrap">
          {[
            { n: 1, label: "Service" },
            { n: 2, label: "Staff" },
            { n: 3, label: "Time" },
            { n: 4, label: "Details" },
          ].map(s => (
            <span
              key={s.n}
              className="px-2 py-1 rounded-full border"
              style={step >= (s.n as any) ? { background: brand, color: "#fff", borderColor: brand } : {}}
            >
              {s.n}. {s.label}
            </span>
          ))}
        </div>

        {/* Step 1: service */}
        {step === 1 && (
          <div className="space-y-2">
            <h2 className="text-lg font-medium">Choose a service</h2>
            {services.length === 0 && <p className="text-sm text-gray-500">No services available.</p>}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {services.map(s => (
                <button
                  key={s.id}
                  onClick={() => { setSelectedService(s); setStep(2); }}
                  className="text-start w-full border rounded-md p-3 hover:bg-gray-50"
                  style={{ borderColor: selectedService?.id === s.id ? brand : undefined }}
                >
                  <div className="font-medium">{s.name}</div>
                  <div className="text-xs text-gray-600">
                    {s.duration_minutes} min · {s.price.toFixed(2)}
                  </div>
                  {s.description && <div className="text-xs mt-1 text-gray-500">{s.description}</div>}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 2: staff */}
        {step === 2 && (
          <div className="space-y-2">
            <h2 className="text-lg font-medium">Choose a staff member</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {staff.map(s => (
                <button
                  key={s.id}
                  onClick={() => { setSelectedStaff(s); setStep(3); }}
                  className="text-start w-full border rounded-md p-3 hover:bg-gray-50"
                  style={{ borderColor: selectedStaff?.id === s.id ? brand : undefined }}
                >
                  <div className="font-medium">{s.name}</div>
                  {s.role && <div className="text-xs text-gray-600">{s.role}</div>}
                </button>
              ))}
            </div>
            <button onClick={() => setStep(1)} className="text-sm underline">Back</button>
          </div>
        )}

        {/* Step 3: time */}
        {step === 3 && (
          <div className="space-y-3">
            <h2 className="text-lg font-medium">Pick a time</h2>
            <input
              type="date"
              value={day}
              onChange={e => setDay(e.target.value)}
              className="border rounded-md px-3 py-2 text-sm"
            />
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 max-h-64 overflow-y-auto">
              {slots.length === 0 && <p className="text-sm text-gray-500 col-span-full">No free slots for this day.</p>}
              {slots.map(s => (
                <button
                  key={s.start}
                  onClick={() => { setSelectedSlot(s); setStep(4); }}
                  className="border rounded-md p-2 text-sm hover:bg-gray-50"
                  style={{ borderColor: selectedSlot?.start === s.start ? brand : undefined }}
                >
                  {new Date(s.start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </button>
              ))}
            </div>
            <button onClick={() => setStep(2)} className="text-sm underline">Back</button>
          </div>
        )}

        {/* Step 4: details */}
        {step === 4 && (
          <div className="space-y-3">
            <h2 className="text-lg font-medium">Your details</h2>
            <input
              type="text"
              placeholder="Full name"
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full border rounded-md px-3 py-2 text-sm"
            />
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full border rounded-md px-3 py-2 text-sm"
            />
            <input
              type="tel"
              placeholder="Phone (optional)"
              value={phone}
              onChange={e => setPhone(e.target.value)}
              className="w-full border rounded-md px-3 py-2 text-sm"
            />
            <textarea
              placeholder="Notes (optional)"
              value={notes}
              onChange={e => setNotes(e.target.value)}
              rows={2}
              className="w-full border rounded-md px-3 py-2 text-sm"
            />
            {error && <p className="text-sm text-red-600">{error}</p>}
            <div className="flex justify-between">
              <button onClick={() => setStep(3)} className="text-sm underline">Back</button>
              <button
                onClick={() => void book()}
                disabled={submitting || !name.trim() || !email.trim()}
                className="rounded-md px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                style={{ background: brand }}
              >
                {submitting ? "Booking…" : "Confirm booking"}
              </button>
            </div>
          </div>
        )}

        {/* Step 5: confirmed */}
        {step === 5 && confirmed && (
          <div className="space-y-2 text-center py-8">
            <div className="text-2xl" style={{ color: brand }}>✓</div>
            <h2 className="text-lg font-medium">You're booked!</h2>
            <p className="text-sm text-gray-600">
              {confirmed.service_name} with {confirmed.staff_name} on{" "}
              {new Date(confirmed.start_time).toLocaleString()}.
            </p>
            <p className="text-xs text-gray-500">
              A confirmation email is on its way to {email}.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
