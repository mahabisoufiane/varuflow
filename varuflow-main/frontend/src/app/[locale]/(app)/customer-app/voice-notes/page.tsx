"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";
import {
  PlusCircle, Mic, RefreshCw, ChevronDown, ChevronUp, Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface VoiceNote {
  id: string;
  sender_type: "customer" | "staff";
  customer_id: string | null;
  thread_id: string | null;
  audio_url: string;
  duration_seconds: number | null;
  transcription: string | null;
  is_read: boolean;
  created_at: string;
}

type SenderFilter = "all" | "customer" | "staff";

const SENDER_TABS: { value: SenderFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "customer", label: "Customer" },
  { value: "staff", label: "Staff" },
];

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function formatDuration(secs: number | null): string {
  if (secs === null) return "—";
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function truncate(str: string | null, n: number): string {
  if (!str) return "—";
  return str.length > n ? str.slice(0, n) + "…" : str;
}

export default function VoiceNotesPage() {
  const [notes, setNotes] = useState<VoiceNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [senderFilter, setSenderFilter] = useState<SenderFilter>("all");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [transcriptionDraft, setTranscriptionDraft] = useState<Record<string, string>>({});
  const [showTranscribeInput, setShowTranscribeInput] = useState<Record<string, boolean>>({});
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Upload form
  const [showNew, setShowNew] = useState(false);
  const [newForm, setNewForm] = useState({
    sender_type: "customer",
    audio_url: "",
    duration_seconds: "",
    customer_id: "",
    thread_id: "",
  });

  async function load() {
    setLoading(true);
    try {
      const query = unreadOnly ? "?is_read=false" : "";
      const data = await api.get<VoiceNote[]>(`/api/voice-notes${query}`);
      setNotes(data);
    } catch {
      toast.error("Failed to load voice notes");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function markRead(id: string) {
    setActionLoading(id + "_read");
    try {
      await api.patch(`/api/voice-notes/${id}/read`, {});
      setNotes((prev) => prev.map((n) => n.id === id ? { ...n, is_read: true } : n));
      toast.success("Marked as read");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function addTranscription(id: string) {
    const text = transcriptionDraft[id]?.trim();
    if (!text) { toast.error("Transcription text is required"); return; }
    setActionLoading(id + "_transcribe");
    try {
      await api.patch(`/api/voice-notes/${id}/transcribe`, { transcription: text });
      toast.success("Transcription saved");
      setNotes((prev) =>
        prev.map((n) => n.id === id ? { ...n, transcription: text } : n)
      );
      setShowTranscribeInput((prev) => ({ ...prev, [id]: false }));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function deleteNote(id: string) {
    setActionLoading(id + "_delete");
    try {
      await api.delete(`/api/voice-notes/${id}`);
      setNotes((prev) => prev.filter((n) => n.id !== id));
      if (expandedId === id) setExpandedId(null);
      toast.success("Voice note deleted");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function uploadNote() {
    if (!newForm.audio_url.trim()) { toast.error("Audio URL is required"); return; }
    setActionLoading("upload");
    try {
      await api.post("/api/voice-notes", {
        sender_type: newForm.sender_type,
        audio_url: newForm.audio_url,
        duration_seconds: newForm.duration_seconds ? parseInt(newForm.duration_seconds) : null,
        customer_id: newForm.customer_id || null,
        thread_id: newForm.thread_id || null,
      });
      toast.success("Voice note uploaded");
      setShowNew(false);
      setNewForm({ sender_type: "customer", audio_url: "", duration_seconds: "", customer_id: "", thread_id: "" });
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  const filtered = notes.filter((n) => {
    if (senderFilter !== "all" && n.sender_type !== senderFilter) return false;
    if (unreadOnly && n.is_read) return false;
    return true;
  });

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Voice Notes</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Inbox of all voice messages from customers and staff.
          </p>
        </div>
        <Button onClick={() => setShowNew(true)} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> Upload Voice Note
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-1 border-b">
          {SENDER_TABS.map((t) => (
            <button
              key={t.value}
              type="button"
              onClick={() => setSenderFilter(t.value)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                senderFilter === t.value
                  ? "border-[#1a2332] text-[#1a2332]"
                  : "border-transparent text-muted-foreground hover:text-gray-700"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(e) => setUnreadOnly(e.target.checked)}
            className="rounded border-gray-300 focus:ring-[#1a2332]"
          />
          Unread only
        </label>
      </div>

      {/* Upload form */}
      {showNew && (
        <div className="rounded-xl border border-[#1a2332]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Upload Voice Note</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Sender Type</label>
              <select
                value={newForm.sender_type}
                onChange={(e) => setNewForm((f) => ({ ...f, sender_type: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332] bg-white"
              >
                <option value="customer">Customer</option>
                <option value="staff">Staff</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Duration (seconds)</label>
              <input
                type="number"
                value={newForm.duration_seconds}
                onChange={(e) => setNewForm((f) => ({ ...f, duration_seconds: e.target.value }))}
                placeholder="32"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
              />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Audio URL *</label>
            <input
              value={newForm.audio_url}
              onChange={(e) => setNewForm((f) => ({ ...f, audio_url: e.target.value }))}
              placeholder="https://…"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Customer ID (optional)</label>
              <input
                value={newForm.customer_id}
                onChange={(e) => setNewForm((f) => ({ ...f, customer_id: e.target.value }))}
                placeholder="UUID"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Thread ID (optional)</label>
              <input
                value={newForm.thread_id}
                onChange={(e) => setNewForm((f) => ({ ...f, thread_id: e.target.value }))}
                placeholder="UUID"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancel</Button>
            <Button
              disabled={actionLoading === "upload"}
              onClick={uploadNote}
              className="bg-[#1a2332] hover:bg-[#2a3342] text-white"
            >
              {actionLoading === "upload" ? "Uploading…" : "Upload"}
            </Button>
          </div>
        </div>
      )}

      {/* Notes list */}
      {loading && notes.length === 0 ? (
        <div className="text-center py-12">
          <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border bg-white shadow-sm py-12 text-center">
          <Mic className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-gray-600 font-medium">No voice notes yet</p>
          <p className="text-sm text-muted-foreground mt-1">
            Customers can send voice messages from the mobile app.
          </p>
        </div>
      ) : (
        <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
          {filtered.map((note) => {
            const isExpanded = expandedId === note.id;
            return (
              <div key={note.id}>
                <button
                  type="button"
                  onClick={() => setExpandedId(isExpanded ? null : note.id)}
                  className="w-full flex items-center gap-4 px-5 py-4 hover:bg-gray-50 transition-colors text-left"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                      <span className={styles[note.sender_type === "customer" ? "senderCustomer" : "senderStaff"]}>
                        {note.sender_type}
                      </span>
                      <p className="text-sm font-medium text-gray-900">
                        {truncate(note.customer_id, 18)}
                      </p>
                      <span className={`h-2 w-2 rounded-full flex-shrink-0 ${note.is_read ? "bg-green-400" : "bg-amber-400"}`} />
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {relativeTime(note.created_at)} · {formatDuration(note.duration_seconds)}
                    </p>
                  </div>
                  <a
                    href={note.audio_url}
                    target="_blank"
                    rel="noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    Play
                  </a>
                  {isExpanded ? (
                    <ChevronUp className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                  )}
                </button>

                {isExpanded && (
                  <div className="border-t border-gray-100 bg-gray-50 px-5 py-4 space-y-3">
                    {note.transcription ? (
                      <div className="rounded-md bg-gray-100 border border-gray-200 px-3 py-2.5">
                        <p className="text-xs font-medium text-gray-500 mb-1">Transcription</p>
                        <p className="text-sm text-gray-800">{note.transcription}</p>
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground italic">No transcription available.</p>
                    )}

                    {showTranscribeInput[note.id] ? (
                      <div className="space-y-2">
                        <textarea
                          value={transcriptionDraft[note.id] ?? ""}
                          onChange={(e) =>
                            setTranscriptionDraft((prev) => ({ ...prev, [note.id]: e.target.value }))
                          }
                          rows={3}
                          placeholder="Type transcription…"
                          className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332] bg-white"
                        />
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setShowTranscribeInput((prev) => ({ ...prev, [note.id]: false }))}
                          >
                            Cancel
                          </Button>
                          <Button
                            size="sm"
                            disabled={actionLoading === note.id + "_transcribe"}
                            onClick={() => addTranscription(note.id)}
                            className="bg-[#1a2332] hover:bg-[#2a3342] text-white"
                          >
                            {actionLoading === note.id + "_transcribe" ? "Saving…" : "Save"}
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setShowTranscribeInput((prev) => ({ ...prev, [note.id]: true }))}
                      >
                        {note.transcription ? "Edit Transcription" : "Add Transcription"}
                      </Button>
                    )}

                    <div className="flex items-center gap-2">
                      {!note.is_read && (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={actionLoading === note.id + "_read"}
                          onClick={() => markRead(note.id)}
                          className="border-green-200 text-green-700 hover:bg-green-50"
                        >
                          {actionLoading === note.id + "_read" ? (
                            <RefreshCw className="h-3 w-3 animate-spin" />
                          ) : "Mark Read"}
                        </Button>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={actionLoading === note.id + "_delete"}
                        onClick={() => deleteNote(note.id)}
                        className="border-red-200 text-red-600 hover:bg-red-50 gap-1"
                      >
                        {actionLoading === note.id + "_delete" ? (
                          <RefreshCw className="h-3 w-3 animate-spin" />
                        ) : (
                          <Trash2 className="h-3.5 w-3.5" />
                        )}
                        Delete
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
