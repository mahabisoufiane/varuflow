"use client";

import { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import { Mic, Square, Trash2, FileText, Play } from "lucide-react";

interface VoiceNote { id: string; entity_type: string; entity_id: string; file_url: string; duration_seconds?: number; transcription?: string; created_at: string }

export default function VoiceNotesPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL!;
  const [notes, setNotes] = useState<VoiceNote[]>([]);
  const [recording, setRecording] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [transcribing, setTranscribing] = useState<string | null>(null);
  const [form, setForm] = useState({ entity_type: "customer", entity_id: "" });
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetch_ = (url: string, opts?: RequestInit) =>
    fetch(`${apiBase}${url}`, { credentials: "include", ...opts });

  async function load() {
    const res = await fetch_("/api/mobile/voice-notes?limit=50");
    if (res.ok) setNotes((await res.json()).notes);
  }

  useEffect(() => { load(); }, []);

  async function startRecording() {
    if (!form.entity_id) { toast.error("Enter an entity ID first"); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream, { mimeType: "audio/webm" });
      chunksRef.current = [];
      mr.ondataavailable = e => chunksRef.current.push(e.data);
      mr.start();
      mediaRecorderRef.current = mr;
      setRecording(true);
      setElapsed(0);
      timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000);
    } catch {
      toast.error("Microphone access denied");
    }
  }

  async function stopRecording() {
    const mr = mediaRecorderRef.current;
    if (!mr) return;
    mr.stop();
    mr.stream.getTracks().forEach(t => t.stop());
    setRecording(false);
    if (timerRef.current) clearInterval(timerRef.current);

    await new Promise<void>(resolve => { mr.onstop = () => resolve(); });

    const blob = new Blob(chunksRef.current, { type: "audio/webm" });
    await uploadAndIndex(blob, elapsed);
  }

  async function uploadAndIndex(blob: Blob, duration: number) {
    setUploading(true);
    try {
      // Upload to Supabase Storage via signed URL (frontend direct upload)
      // Simplified: here we just create a local blob URL for demo purposes
      // In production, upload to Supabase Storage and get the public URL
      const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
      const fileName = `voice-notes/${Date.now()}.webm`;
      let fileUrl = URL.createObjectURL(blob); // placeholder for demo

      if (supabaseUrl) {
        try {
          const { createClient } = await import("@supabase/supabase-js");
          const sb = createClient(supabaseUrl, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!);
          const { data, error } = await sb.storage.from("voice-notes").upload(fileName, blob, { contentType: "audio/webm" });
          if (!error && data) {
            const { data: { publicUrl } } = sb.storage.from("voice-notes").getPublicUrl(fileName);
            fileUrl = publicUrl;
          }
        } catch {}
      }

      const res = await fetch_("/api/mobile/voice-notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entity_type: form.entity_type,
          entity_id: form.entity_id,
          file_url: fileUrl,
          duration_seconds: duration,
        }),
      });

      if (res.ok) {
        toast.success("Voice note saved");
        await load();
      } else {
        const err = await res.json();
        toast.error(err.detail || "Failed to save");
      }
    } catch {
      toast.error("Upload failed");
    }
    setUploading(false);
  }

  async function transcribe(id: string) {
    setTranscribing(id);
    const res = await fetch_(`/api/mobile/voice-notes/${id}/transcribe`, { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      setNotes(n => n.map(x => x.id === id ? { ...x, transcription: data.transcription } : x));
      toast.success("Transcription complete");
    } else {
      const err = await res.json();
      toast.error(err.detail || "Transcription failed");
    }
    setTranscribing(null);
  }

  async function deleteNote(id: string) {
    await fetch_(`/api/mobile/voice-notes/${id}`, { method: "DELETE" });
    setNotes(n => n.filter(x => x.id !== id));
    toast.success("Deleted");
  }

  const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Voice Notes</h1>
        <p className="mt-1 text-sm text-gray-500">Record and attach audio notes to customers, suppliers, or route stops.</p>
      </div>

      {/* Record */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 space-y-4">
        <h2 className="text-sm font-semibold text-gray-700">New Recording</h2>
        <div className="grid grid-cols-2 gap-3">
          <select className="input" value={form.entity_type} onChange={e => setForm(f => ({ ...f, entity_type: e.target.value }))}>
            <option value="customer">Customer</option>
            <option value="supplier">Supplier</option>
            <option value="route_stop">Route Stop</option>
            <option value="invoice">Invoice</option>
          </select>
          <input className="input" placeholder="Entity ID (UUID)" value={form.entity_id} onChange={e => setForm(f => ({ ...f, entity_id: e.target.value }))} />
        </div>

        <div className="flex items-center gap-4">
          {!recording ? (
            <button onClick={startRecording} disabled={uploading} className="btn-primary flex items-center gap-2">
              <Mic className="h-4 w-4" /> Start Recording
            </button>
          ) : (
            <button onClick={stopRecording} className="btn-danger flex items-center gap-2">
              <Square className="h-4 w-4" /> Stop — {fmt(elapsed)}
            </button>
          )}
          {uploading && <span className="text-sm text-gray-500 animate-pulse">Saving…</span>}
        </div>
      </div>

      {/* List */}
      {notes.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 p-12 text-center text-sm text-gray-400">
          No voice notes yet.
        </div>
      ) : (
        <div className="space-y-3">
          {notes.map(n => (
            <div key={n.id} className="rounded-xl border border-gray-200 bg-white p-4 space-y-2">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Mic className="h-4 w-4 text-amber-500 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-gray-900 capitalize">{n.entity_type}</p>
                    <p className="text-xs text-gray-500">
                      {n.duration_seconds ? `${n.duration_seconds}s · ` : ""}
                      {new Date(n.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  <a href={n.file_url} target="_blank" rel="noopener noreferrer" className="btn-sm-outline">
                    <Play className="h-3.5 w-3.5" />
                  </a>
                  {!n.transcription && (
                    <button onClick={() => transcribe(n.id)} disabled={transcribing === n.id} className="btn-sm-outline">
                      <FileText className="h-3.5 w-3.5" />
                      {transcribing === n.id ? "…" : "Transcribe"}
                    </button>
                  )}
                  <button onClick={() => deleteNote(n.id)} className="btn-sm-danger-outline">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
              {n.transcription && (
                <div className="rounded-lg bg-gray-50 p-3">
                  <p className="text-xs text-gray-500 font-medium mb-1">Transcription</p>
                  <p className="text-sm text-gray-700">{n.transcription}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
