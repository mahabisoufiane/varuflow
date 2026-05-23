"use client";

import { useEffect, useState } from "react";
import { Calendar, Clock, MapPin, Loader2, CheckCircle } from "lucide-react";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

interface MeetingInfo {
  title: string;
  description: string | null;
  duration_minutes: number;
  location: string | null;
}

export default function MeetPage({ params }: { params: { slug: string } }) {
  const { slug } = params;
  const [info, setInfo] = useState<MeetingInfo | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [selectedDay, setSelectedDay] = useState("");
  const [slots, setSlots] = useState<string[]>([]);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [notes, setNotes] = useState("");
  const [booking, setBooking] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${BASE}/api/meet/${slug}`)
      .then((r) => {
        if (r.status === 404) { setNotFound(true); return null; }
        return r.json();
      })
      .then((d) => d && setInfo(d))
      .catch(() => setNotFound(true));
  }, [slug]);

  async function loadSlots(day: string) {
    setSelectedDay(day);
    setSelectedSlot("");
    setSlots([]);
    setLoadingSlots(true);
    try {
      const r = await fetch(`${BASE}/api/meet/${slug}/slots?day=${day}`);
      const d = await r.json();
      setSlots(d.slots ?? []);
    } catch {
      setSlots([]);
    } finally {
      setLoadingSlots(false);
    }
  }

  async function handleBook() {
    if (!selectedSlot || !name || !email) {
      setError("Please fill in all required fields.");
      return;
    }
    setError("");
    setBooking(true);
    try {
      const r = await fetch(`${BASE}/api/meet/${slug}/book`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, notes, start_time: selectedSlot }),
      });
      if (!r.ok) throw new Error("Booking failed");
      setConfirmed(true);
    } catch {
      setError("Booking failed. Please try again.");
    } finally {
      setBooking(false);
    }
  }

  // Generate next 14 days for date picker
  const days: string[] = [];
  for (let i = 0; i < 14; i++) {
    const d = new Date();
    d.setDate(d.getDate() + i);
    days.push(d.toISOString().slice(0, 10));
  }

  if (notFound) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-500">Meeting link not found.</p>
      </div>
    );
  }

  if (!info) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    );
  }

  if (confirmed) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4 text-center px-4">
        <CheckCircle className="h-12 w-12 text-green-500" />
        <h1 className="text-2xl font-semibold">Meeting confirmed!</h1>
        <p className="text-gray-500">A confirmation has been sent to {email}.</p>
        <p className="text-sm text-gray-400">
          {info.title} · {new Date(selectedSlot).toLocaleString()} · {info.duration_minutes} min
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      {/* Header */}
      <div className="bg-white border rounded-2xl p-6 mb-6">
        <h1 className="text-2xl font-semibold mb-1">{info.title}</h1>
        {info.description && <p className="text-gray-500 text-sm mb-3">{info.description}</p>}
        <div className="flex flex-wrap gap-4 text-sm text-gray-600">
          <span className="flex items-center gap-1.5">
            <Clock className="h-4 w-4" /> {info.duration_minutes} min
          </span>
          {info.location && (
            <span className="flex items-center gap-1.5">
              <MapPin className="h-4 w-4" /> {info.location}
            </span>
          )}
        </div>
      </div>

      {/* Step 1: Pick a day */}
      <div className="bg-white border rounded-2xl p-6 mb-4">
        <h2 className="font-medium mb-3 flex items-center gap-2">
          <Calendar className="h-4 w-4" /> Select a date
        </h2>
        <div className="flex flex-wrap gap-2">
          {days.map((d) => (
            <button
              key={d}
              onClick={() => loadSlots(d)}
              className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                selectedDay === d
                  ? "bg-indigo-600 text-white border-indigo-600"
                  : "hover:bg-gray-50 border-gray-200"
              }`}
            >
              {new Date(d + "T12:00:00").toLocaleDateString("en", { weekday: "short", month: "short", day: "numeric" })}
            </button>
          ))}
        </div>
      </div>

      {/* Step 2: Pick a slot */}
      {selectedDay && (
        <div className="bg-white border rounded-2xl p-6 mb-4">
          <h2 className="font-medium mb-3">Available times</h2>
          {loadingSlots ? (
            <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
          ) : slots.length === 0 ? (
            <p className="text-sm text-gray-400">No slots available on this day.</p>
          ) : (
            <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
              {slots.map((s) => (
                <button
                  key={s}
                  onClick={() => setSelectedSlot(s)}
                  className={`py-2 rounded-lg text-sm border transition-colors ${
                    selectedSlot === s
                      ? "bg-indigo-600 text-white border-indigo-600"
                      : "hover:bg-gray-50 border-gray-200"
                  }`}
                >
                  {new Date(s).toLocaleTimeString("en", { hour: "2-digit", minute: "2-digit" })}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Step 3: Contact form */}
      {selectedSlot && (
        <div className="bg-white border rounded-2xl p-6">
          <h2 className="font-medium mb-4">Your details</h2>
          <div className="space-y-3">
            <div>
              <label className="text-sm font-medium text-gray-700">Name *</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">Email *</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">Notes</label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 resize-none"
              />
            </div>
          </div>
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
          <button
            onClick={handleBook}
            disabled={booking}
            className="mt-4 w-full flex items-center justify-center gap-2 bg-indigo-600 text-white rounded-lg py-2.5 text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {booking ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Confirm booking
          </button>
        </div>
      )}
    </div>
  );
}
