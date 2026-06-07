"use client";

import { api } from "@/lib/api-client";
import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { toast } from "sonner";
import {
  FileSignature, Send, Bell, X, ChevronDown, ChevronUp,
  RefreshCw, Plus, Check, Clock, AlertTriangle, Shield,
  Download, UserCheck, UserX
} from "lucide-react";
import styles from "./page.module.scss";

interface Signatory {
  id: string; name: string; email: string; role?: string;
  sign_order: number; status: string;
  signed_at?: string; declined_at?: string; token: string;
}
interface AuditEntry {
  event_type: string; actor_email?: string; actor_name?: string;
  ip_address?: string; created_at: string;
}
interface SignRequest {
  id: string; title: string; message?: string;
  document_id?: string; status: string;
  reminder_days?: number; expires_at?: string;
  completed_at?: string; signed_pdf_url?: string;
  created_at: string;
  signatories: Signatory[];
  audit_entries: AuditEntry[];
}

const STATUS_STYLE: Record<string, string> = {
  draft:            "bg-gray-100 text-gray-600",
  sent:             "bg-blue-100 text-blue-700",
  partially_signed: "bg-amber-100 text-amber-700",
  fully_signed:     "bg-green-100 text-green-700",
  declined:         "bg-red-100 text-red-700",
  expired:          "bg-orange-100 text-orange-700",
  cancelled:        "bg-gray-100 text-gray-500",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  draft:            "statusDraft",
  sent:             "statusSent",
  partially_signed: "statusPartiallySigned",
  fully_signed:     "statusFullySigned",
  declined:         "statusDeclined",
  expired:          "statusExpired",
  cancelled:        "statusCancelled",
};

const SIG_STATUS_STYLE: Record<string, string> = {
  pending: "text-amber-600",
  signed:  "text-green-600",
  declined: "text-red-600",
};

const SIG_MODULE: Record<string, keyof typeof styles> = {
  pending:  "sigPending",
  signed:   "sigSigned",
  declined: "sigDeclined",
};

export default function ContractSigningPage() {
  const router = useRouter();
  const params = useParams();
  const locale = params.locale as string;

  const [requests, setRequests] = useState<SignRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("sent");
  const [showCreate, setShowCreate] = useState(false);
  const [acting, setActing] = useState<string | null>(null);

  // Create form
  const [form, setForm] = useState({
    title: "", message: "", expires_in_days: "30", reminder_days: "",
  });
  const [signatories, setSignatories] = useState([{ name: "", email: "", role: "" }]);

  async function load() {
    try {
      const qs = statusFilter ? `?status=${statusFilter}` : "";
      const data = await api.get(`/api/esign/requests${qs}`);
      setRequests(data.items ?? data);
    } catch (err: any) {
      if (err?.status === 401) router.push(`/${locale}/auth/login`);
      else toast.error("Failed to load signing requests");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [statusFilter]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.post("/api/esign/requests", {
        title: form.title,
        message: form.message || undefined,
        expires_in_days: parseInt(form.expires_in_days),
        reminder_days: form.reminder_days ? parseInt(form.reminder_days) : undefined,
        signatories: signatories.filter(s => s.name && s.email).map(s => ({
          name: s.name, email: s.email, role: s.role || undefined,
        })),
      });
      toast.success("Signing request created");
      setShowCreate(false);
      setForm({ title: "", message: "", expires_in_days: "30", reminder_days: "" });
      setSignatories([{ name: "", email: "", role: "" }]);
      load();
    } catch {
      toast.error("Failed to create signing request");
    }
  }

  async function send(id: string) {
    setActing(id + "_send");
    try {
      const result = await api.post(`/api/esign/requests/${id}/send`, {});
      toast.success(`Invitations sent to ${result.sent_to?.length ?? 0} signatories`);
      load();
    } catch {
      toast.error("Failed to send invitations");
    } finally {
      setActing(null);
    }
  }

  async function remind(id: string) {
    setActing(id + "_remind");
    try {
      const result = await api.post(`/api/esign/requests/${id}/remind`, {});
      toast.success(`Reminders sent to ${result.reminded?.length ?? 0} pending signatories`);
    } catch {
      toast.error("Failed to send reminders");
    } finally {
      setActing(null);
    }
  }

  async function cancel(id: string) {
    setActing(id + "_cancel");
    try {
      await api.patch(`/api/esign/requests/${id}/cancel`, {});
      toast.success("Request cancelled");
      load();
    } catch {
      toast.error("Failed to cancel request");
    } finally {
      setActing(null);
    }
  }

  async function downloadCert(id: string) {
    try {
      const text = await api.get(`/api/esign/requests/${id}/certificate`);
      const blob = new Blob([text], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `audit-certificate-${id}.txt`; a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Failed to download certificate");
    }
  }

  const statusCounts = {
    all: requests.length,
    sent: requests.filter(r => ["sent", "partially_signed"].includes(r.status)).length,
    fully_signed: requests.filter(r => r.status === "fully_signed").length,
    declined: requests.filter(r => ["declined", "cancelled"].includes(r.status)).length,
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Digital Contract Signing</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Send contracts for e-signature — legally binding with full audit trail
          </p>
        </div>
        <button className="btn-primary flex items-center gap-2" onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4" /> New Signing Request
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: "Awaiting Signature", value: statusCounts.sent, Icon: Clock, color: "text-amber-600" },
          { label: "Fully Signed", value: statusCounts.fully_signed, Icon: Check, color: "text-green-600" },
          { label: "Declined / Cancelled", value: statusCounts.declined, Icon: X, color: "text-red-600" },
          { label: "Total Requests", value: requests.length, Icon: FileSignature, color: "" },
        ].map(({ label, value, Icon, color }) => (
          <div key={label} className="rounded-2xl border bg-card p-4">
            <div className="flex items-center gap-2">
              <Icon className={`h-4 w-4 ${color || "text-muted-foreground"}`} />
              <p className="text-xs text-muted-foreground">{label}</p>
            </div>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Filter */}
      <div className="flex gap-3 flex-wrap">
        <select className="input text-sm py-1.5 h-9" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="">All</option>
          <option value="draft">Draft</option>
          <option value="sent">Sent</option>
          <option value="partially_signed">Partially Signed</option>
          <option value="fully_signed">Fully Signed</option>
          <option value="declined">Declined</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      {/* Requests list */}
      {loading ? (
        <div className="flex justify-center py-16">
          <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : requests.length === 0 ? (
        <div className="rounded-2xl border bg-card flex flex-col items-center justify-center py-20 text-center">
          <FileSignature className="h-12 w-12 text-muted-foreground mb-4" />
          <p className="font-medium">No signing requests</p>
          <p className="text-sm text-muted-foreground mt-1">Create one to start collecting e-signatures</p>
        </div>
      ) : (
        <div className="space-y-2">
          {requests.map(req => (
            <div key={req.id} className="rounded-2xl border bg-card overflow-hidden">
              <div
                className="flex items-center gap-3 p-4 cursor-pointer hover:bg-muted/30 transition-colors"
                onClick={() => setExpanded(expanded === req.id ? null : req.id)}
              >
                <FileSignature className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                <p className="flex-1 text-sm font-medium truncate">{req.title}</p>
                <span className={styles[STATUS_MODULE[req.status] ?? "statusDraft"]}>
                  {req.status.replace(/_/g, " ")}
                </span>
                <span className="text-xs text-muted-foreground">
                  {req.signatories.filter(s => s.status === "signed").length}/{req.signatories.length} signed
                </span>
                <span className="text-xs text-muted-foreground">
                  {new Date(req.created_at).toLocaleDateString("sv-SE")}
                </span>
                {expanded === req.id ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
              </div>

              {expanded === req.id && (
                <div className="border-t px-4 pb-4 pt-3 space-y-4">
                  {req.message && <p className="text-sm text-muted-foreground">{req.message}</p>}

                  {/* Signatories */}
                  <div>
                    <p className="text-xs font-semibold text-muted-foreground mb-2">SIGNATORIES</p>
                    <div className="space-y-1">
                      {req.signatories.map(sig => (
                        <div key={sig.id} className="flex items-center gap-3 text-sm">
                          {sig.status === "signed" ? <UserCheck className="h-4 w-4 text-green-600" /> :
                           sig.status === "declined" ? <UserX className="h-4 w-4 text-red-500" /> :
                           <Clock className="h-4 w-4 text-amber-500" />}
                          <span className="font-medium">{sig.name}</span>
                          <span className="text-muted-foreground">{sig.email}</span>
                          {sig.role && <span className="text-xs border rounded px-1">{sig.role}</span>}
                          <span className={styles[SIG_MODULE[sig.status] ?? "sigPending"]}>
                            {sig.status}
                            {sig.signed_at && ` · ${new Date(sig.signed_at).toLocaleDateString("sv-SE")}`}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Audit trail */}
                  {req.audit_entries.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-muted-foreground mb-2">AUDIT TRAIL</p>
                      <div className="space-y-1 bg-muted/30 rounded-xl p-3">
                        {req.audit_entries.slice(0, 8).map((e, i) => (
                          <div key={i} className="flex gap-2 text-xs text-muted-foreground">
                            <span className="font-mono">{new Date(e.created_at).toLocaleString("sv-SE")}</span>
                            <span className="font-medium text-foreground">{e.event_type}</span>
                            {e.actor_email && <span>{e.actor_email}</span>}
                            {e.ip_address && <span className="ml-auto font-mono">{e.ip_address}</span>}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex gap-2 flex-wrap">
                    {req.status === "draft" && (
                      <button
                        className="btn-primary text-xs flex items-center gap-1.5"
                        onClick={() => send(req.id)}
                        disabled={acting === req.id + "_send"}
                      >
                        {acting === req.id + "_send" ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Send className="h-3 w-3" />}
                        Send for Signature
                      </button>
                    )}
                    {["sent", "partially_signed"].includes(req.status) && (
                      <>
                        <button
                          className="btn-secondary text-xs flex items-center gap-1.5"
                          onClick={() => remind(req.id)}
                          disabled={acting === req.id + "_remind"}
                        >
                          <Bell className="h-3 w-3" /> Remind Pending
                        </button>
                        <button
                          className="btn-secondary text-xs flex items-center gap-1.5 text-red-600 hover:text-red-700"
                          onClick={() => cancel(req.id)}
                          disabled={acting === req.id + "_cancel"}
                        >
                          <X className="h-3 w-3" /> Cancel
                        </button>
                      </>
                    )}
                    {req.status === "fully_signed" && (
                      <button
                        className="btn-secondary text-xs flex items-center gap-1.5"
                        onClick={() => downloadCert(req.id)}
                      >
                        <Download className="h-3 w-3" /> Audit Certificate
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-background rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">New Signing Request</h2>
              <button onClick={() => setShowCreate(false)}><X className="h-4 w-4" /></button>
            </div>
            <form onSubmit={create} className="space-y-4">
              <div>
                <label className="text-sm font-medium">Document Title *</label>
                <input required className="input mt-1 w-full" placeholder="e.g. Supply Agreement 2026"
                  value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} />
              </div>
              <div>
                <label className="text-sm font-medium">Message to Signatories</label>
                <textarea className="input mt-1 w-full h-20 resize-none" placeholder="Optional message…"
                  value={form.message} onChange={e => setForm(f => ({ ...f, message: e.target.value }))} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm font-medium">Expires in (days)</label>
                  <input type="number" min="1" className="input mt-1 w-full"
                    value={form.expires_in_days} onChange={e => setForm(f => ({ ...f, expires_in_days: e.target.value }))} />
                </div>
                <div>
                  <label className="text-sm font-medium">Reminder after (days)</label>
                  <input type="number" min="1" className="input mt-1 w-full" placeholder="e.g. 3"
                    value={form.reminder_days} onChange={e => setForm(f => ({ ...f, reminder_days: e.target.value }))} />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium">Signatories</label>
                  <button type="button" className="text-xs text-primary hover:underline"
                    onClick={() => setSignatories(s => [...s, { name: "", email: "", role: "" }])}>
                    + Add signatory
                  </button>
                </div>
                <div className="space-y-2">
                  {signatories.map((sig, i) => (
                    <div key={i} className="flex gap-2">
                      <input className="input flex-1 text-sm" placeholder="Name"
                        value={sig.name} onChange={e => setSignatories(s => s.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} />
                      <input className="input flex-1 text-sm" type="email" placeholder="Email"
                        value={sig.email} onChange={e => setSignatories(s => s.map((x, j) => j === i ? { ...x, email: e.target.value } : x))} />
                      <input className="input w-24 text-sm" placeholder="Role"
                        value={sig.role} onChange={e => setSignatories(s => s.map((x, j) => j === i ? { ...x, role: e.target.value } : x))} />
                      {signatories.length > 1 && (
                        <button type="button" onClick={() => setSignatories(s => s.filter((_, j) => j !== i))}>
                          <X className="h-4 w-4 text-red-500" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
              <div className="flex gap-3 pt-1">
                <button type="button" className="btn-secondary flex-1" onClick={() => setShowCreate(false)}>Cancel</button>
                <button type="submit" className="btn-primary flex-1">Create Request</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
