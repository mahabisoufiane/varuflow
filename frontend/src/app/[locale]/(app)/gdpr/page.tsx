"use client";

import { api } from "@/lib/api-client";
import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { toast } from "sonner";
import {
  Shield, Plus, RefreshCw, Check, X, Download,
  AlertTriangle, Clock, ChevronDown, ChevronUp, Mail
} from "lucide-react";

interface ConsentRecord {
  id: string; customer_id: string; consent_type: string;
  status: string; collected_via: string; notes?: string;
  consented_at: string; expires_at?: string;
}
interface DSAR {
  id: string; customer_id?: string; request_type: string;
  requester_name: string; requester_email: string;
  description?: string; status: string; response_notes?: string;
  due_at?: string; completed_at?: string; created_at: string;
}
interface Summary { consent_type: string; status: string; count: number; }

const CONSENT_TYPES = [
  { value: "marketing_email", label: "Marketing Email" },
  { value: "sms_marketing", label: "SMS Marketing" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "data_processing", label: "Data Processing" },
  { value: "analytics_cookies", label: "Analytics Cookies" },
];
const DSAR_TYPES = [
  { value: "access", label: "Right of Access (Art. 15)" },
  { value: "deletion", label: "Right to Erasure (Art. 17)" },
  { value: "rectification", label: "Right to Rectification (Art. 16)" },
  { value: "portability", label: "Right to Portability (Art. 20)" },
  { value: "restriction", label: "Right to Restriction (Art. 18)" },
];
const STATUS_STYLE: Record<string, string> = {
  given:       "bg-green-100 text-green-700",
  withdrawn:   "bg-gray-100 text-gray-500",
  pending:     "bg-amber-100 text-amber-700",
  in_progress: "bg-blue-100 text-blue-700",
  completed:   "bg-green-100 text-green-700",
  rejected:    "bg-red-100 text-red-700",
};

export default function GdprConsentPage() {
  const router = useRouter();
  const params = useParams();
  const locale = params.locale as string;

  const [tab, setTab] = useState<"consent" | "dsar" | "expiring">("consent");
  const [consents, setConsents] = useState<ConsentRecord[]>([]);
  const [dsars, setDsars] = useState<DSAR[]>([]);
  const [expiring, setExpiring] = useState<ConsentRecord[]>([]);
  const [summary, setSummary] = useState<Summary[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  const [consentFilter, setConsentFilter] = useState("");
  const [dsarFilter, setDsarFilter] = useState("");

  // Add consent form
  const [showAddConsent, setShowAddConsent] = useState(false);
  const [consentForm, setConsentForm] = useState({ customer_id: "", consent_type: "marketing_email", collected_via: "staff", notes: "" });

  // Add DSAR form
  const [showAddDsar, setShowAddDsar] = useState(false);
  const [dsarForm, setDsarForm] = useState({ customer_id: "", request_type: "access", requester_name: "", requester_email: "", description: "" });

  const [acting, setActing] = useState<string | null>(null);

  async function loadAll() {
    setLoading(true);
    try {
      const [cData, dData, eData, sData] = await Promise.all([
        api.get(`/api/gdpr/consent${consentFilter ? `?consent_type=${consentFilter}` : ""}`),
        api.get(`/api/gdpr/dsar${dsarFilter ? `?status=${dsarFilter}` : ""}`),
        api.get("/api/gdpr/consent/expiring"),
        api.get("/api/gdpr/consent-summary"),
      ]);
      setConsents(cData.items ?? []);
      setDsars(dData.items ?? []);
      setExpiring(eData.items ?? []);
      setSummary(sData.breakdown ?? []);
    } catch (err: any) {
      if (err?.status === 401) router.push(`/${locale}/auth/login`);
      else toast.error("Failed to load GDPR data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadAll(); }, [consentFilter, dsarFilter]);

  async function addConsent(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.post("/api/gdpr/consent", { ...consentForm, expires_in_days: 730 });
      toast.success("Consent recorded");
      setShowAddConsent(false);
      setConsentForm({ customer_id: "", consent_type: "marketing_email", collected_via: "staff", notes: "" });
      loadAll();
    } catch {
      toast.error("Failed to record consent");
    }
  }

  async function withdrawConsent(id: string) {
    setActing(id);
    try {
      await api.delete(`/api/gdpr/consent/${id}`);
      toast.success("Consent withdrawn");
      loadAll();
    } catch {
      toast.error("Failed to withdraw consent");
    } finally {
      setActing(null);
    }
  }

  async function addDsar(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.post("/api/gdpr/dsar", dsarForm);
      toast.success("DSAR submitted");
      setShowAddDsar(false);
      setDsarForm({ customer_id: "", request_type: "access", requester_name: "", requester_email: "", description: "" });
      loadAll();
    } catch {
      toast.error("Failed to submit DSAR");
    }
  }

  async function completeDsar(id: string) {
    setActing(id);
    try {
      await api.patch(`/api/gdpr/dsar/${id}`, { status: "completed" });
      toast.success("DSAR marked complete");
      loadAll();
    } catch {
      toast.error("Failed to update DSAR");
    } finally {
      setActing(null);
    }
  }

  async function downloadDsar(id: string) {
    try {
      const data = await api.get(`/api/gdpr/dsar/${id}/package`);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `dsar-${id}.json`; a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Failed to download DSAR package");
    }
  }

  // Summary stats
  const totalGiven = summary.filter(s => s.status === "given").reduce((a, b) => a + b.count, 0);
  const totalWithdrawn = summary.filter(s => s.status === "withdrawn").reduce((a, b) => a + b.count, 0);
  const pendingDsars = dsars.filter(d => d.status === "pending").length;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">GDPR Consent Management</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Track customer consents, handle DSARs, and maintain GDPR compliance
          </p>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="rounded-2xl border bg-card p-4">
          <p className="text-xs text-muted-foreground">Active Consents</p>
          <p className="text-2xl font-bold mt-1 text-green-600">{totalGiven}</p>
        </div>
        <div className="rounded-2xl border bg-card p-4">
          <p className="text-xs text-muted-foreground">Withdrawn</p>
          <p className="text-2xl font-bold mt-1">{totalWithdrawn}</p>
        </div>
        <div className="rounded-2xl border bg-card p-4">
          <p className="text-xs text-muted-foreground flex items-center gap-1">
            <AlertTriangle className="h-3 w-3 text-amber-500" /> Expiring Soon
          </p>
          <p className={`text-2xl font-bold mt-1 ${expiring.length > 0 ? "text-amber-600" : ""}`}>{expiring.length}</p>
        </div>
        <div className="rounded-2xl border bg-card p-4">
          <p className="text-xs text-muted-foreground">Open DSARs</p>
          <p className={`text-2xl font-bold mt-1 ${pendingDsars > 0 ? "text-red-600" : ""}`}>{pendingDsars}</p>
        </div>
      </div>

      {/* Expiring alert */}
      {expiring.length > 0 && (
        <div className="flex items-center gap-3 p-4 rounded-2xl bg-amber-50 border border-amber-200 text-amber-800">
          <AlertTriangle className="h-5 w-5 flex-shrink-0" />
          <p className="text-sm font-medium">
            {expiring.length} consent{expiring.length !== 1 ? "s" : ""} expire within 30 days and need revalidation
          </p>
          <button className="ml-auto text-xs underline" onClick={() => setTab("expiring")}>View</button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b">
        {([["consent", "Consent Records"], ["dsar", "DSARs"], ["expiring", "Expiring"]] as const).map(([t, label]) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {label}
            {t === "dsar" && pendingDsars > 0 && (
              <span className="ml-1.5 bg-red-500 text-white text-xs rounded-full px-1.5">{pendingDsars}</span>
            )}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          {/* ── Consent Records tab ── */}
          {tab === "consent" && (
            <div className="space-y-4">
              <div className="flex gap-3 items-center">
                <select className="input text-sm py-1.5 h-9" value={consentFilter} onChange={e => setConsentFilter(e.target.value)}>
                  <option value="">All types</option>
                  {CONSENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
                <button className="btn-primary text-sm flex items-center gap-2 ml-auto" onClick={() => setShowAddConsent(true)}>
                  <Plus className="h-4 w-4" /> Record Consent
                </button>
              </div>
              {consents.length === 0 ? (
                <div className="rounded-2xl border bg-card flex flex-col items-center justify-center py-16 text-center">
                  <Shield className="h-10 w-10 text-muted-foreground mb-3" />
                  <p className="font-medium">No consent records</p>
                </div>
              ) : (
                <div className="rounded-2xl border overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/30">
                      <tr>
                        {["Customer", "Consent Type", "Status", "Via", "Given At", "Expires", ""].map(h => (
                          <th key={h} className="text-left px-4 py-2 text-xs font-medium text-muted-foreground">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {consents.map(c => (
                        <tr key={c.id} className="hover:bg-muted/20">
                          <td className="px-4 py-2 font-mono text-xs">{c.customer_id.slice(0, 8)}…</td>
                          <td className="px-4 py-2">{CONSENT_TYPES.find(t => t.value === c.consent_type)?.label ?? c.consent_type}</td>
                          <td className="px-4 py-2">
                            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_STYLE[c.status] ?? ""}`}>{c.status}</span>
                          </td>
                          <td className="px-4 py-2 text-muted-foreground">{c.collected_via}</td>
                          <td className="px-4 py-2 text-muted-foreground">{new Date(c.consented_at).toLocaleDateString("sv-SE")}</td>
                          <td className="px-4 py-2 text-muted-foreground">
                            {c.expires_at ? new Date(c.expires_at).toLocaleDateString("sv-SE") : "–"}
                          </td>
                          <td className="px-4 py-2">
                            {c.status === "given" && (
                              <button
                                className="text-xs text-red-600 hover:underline"
                                onClick={() => withdrawConsent(c.id)}
                                disabled={acting === c.id}
                              >
                                Withdraw
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* ── DSAR tab ── */}
          {tab === "dsar" && (
            <div className="space-y-4">
              <div className="flex gap-3 items-center">
                <select className="input text-sm py-1.5 h-9" value={dsarFilter} onChange={e => setDsarFilter(e.target.value)}>
                  <option value="">All statuses</option>
                  <option value="pending">Pending</option>
                  <option value="in_progress">In Progress</option>
                  <option value="completed">Completed</option>
                  <option value="rejected">Rejected</option>
                </select>
                <button className="btn-primary text-sm flex items-center gap-2 ml-auto" onClick={() => setShowAddDsar(true)}>
                  <Plus className="h-4 w-4" /> New DSAR
                </button>
              </div>
              {dsars.length === 0 ? (
                <div className="rounded-2xl border bg-card flex flex-col items-center justify-center py-16 text-center">
                  <Shield className="h-10 w-10 text-muted-foreground mb-3" />
                  <p className="font-medium">No data subject requests</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {dsars.map(d => (
                    <div key={d.id} className="rounded-2xl border bg-card overflow-hidden">
                      <div
                        className="flex items-center gap-3 p-4 cursor-pointer hover:bg-muted/30"
                        onClick={() => setExpanded(expanded === d.id ? null : d.id)}
                      >
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_STYLE[d.status] ?? ""}`}>{d.status}</span>
                        <span className="text-xs border rounded px-1.5 py-0.5 text-muted-foreground">{DSAR_TYPES.find(t => t.value === d.request_type)?.label ?? d.request_type}</span>
                        <p className="flex-1 text-sm font-medium">{d.requester_name}</p>
                        <span className="text-xs text-muted-foreground">{d.requester_email}</span>
                        {d.due_at && (
                          <span className={`text-xs flex items-center gap-1 ${new Date(d.due_at) < new Date() ? "text-red-600" : "text-muted-foreground"}`}>
                            <Clock className="h-3 w-3" />
                            Due {new Date(d.due_at).toLocaleDateString("sv-SE")}
                          </span>
                        )}
                        {expanded === d.id ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                      </div>
                      {expanded === d.id && (
                        <div className="border-t px-4 pb-4 pt-3 space-y-3">
                          {d.description && <p className="text-sm text-muted-foreground">{d.description}</p>}
                          {d.response_notes && (
                            <div className="bg-muted/40 rounded-xl p-3 text-sm">{d.response_notes}</div>
                          )}
                          <div className="flex gap-2">
                            <button className="btn-secondary text-xs flex items-center gap-1.5" onClick={() => downloadDsar(d.id)}>
                              <Download className="h-3 w-3" /> Data Package
                            </button>
                            {d.status === "pending" && (
                              <button
                                className="btn-primary text-xs flex items-center gap-1.5"
                                onClick={() => completeDsar(d.id)}
                                disabled={acting === d.id}
                              >
                                <Check className="h-3 w-3" /> Mark Complete
                              </button>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Expiring tab ── */}
          {tab === "expiring" && (
            <div className="space-y-2">
              {expiring.length === 0 ? (
                <div className="rounded-2xl border bg-card flex flex-col items-center justify-center py-16 text-center">
                  <Check className="h-10 w-10 text-green-500 mb-3" />
                  <p className="font-medium">No consents expiring soon</p>
                </div>
              ) : (
                expiring.map(c => (
                  <div key={c.id} className="rounded-2xl border bg-card p-4 flex items-center gap-4">
                    <AlertTriangle className="h-5 w-5 text-amber-500 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium">{CONSENT_TYPES.find(t => t.value === c.consent_type)?.label}</p>
                      <p className="text-xs text-muted-foreground">Customer: {c.customer_id.slice(0, 8)}…</p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs font-medium text-amber-600">Expires {c.expires_at ? new Date(c.expires_at).toLocaleDateString("sv-SE") : "–"}</p>
                    </div>
                    <button className="btn-secondary text-xs flex items-center gap-1"><Mail className="h-3 w-3" /> Revalidate</button>
                  </div>
                ))
              )}
            </div>
          )}
        </>
      )}

      {/* Add consent modal */}
      {showAddConsent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-background rounded-2xl shadow-xl w-full max-w-sm p-6 space-y-4">
            <h2 className="text-lg font-semibold">Record Consent</h2>
            <form onSubmit={addConsent} className="space-y-3">
              <div>
                <label className="text-sm font-medium">Customer ID</label>
                <input required className="input mt-1 w-full" placeholder="Customer UUID"
                  value={consentForm.customer_id} onChange={e => setConsentForm(f => ({ ...f, customer_id: e.target.value }))} />
              </div>
              <div>
                <label className="text-sm font-medium">Consent Type</label>
                <select required className="input mt-1 w-full" value={consentForm.consent_type}
                  onChange={e => setConsentForm(f => ({ ...f, consent_type: e.target.value }))}>
                  {CONSENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">Collected Via</label>
                <select className="input mt-1 w-full" value={consentForm.collected_via}
                  onChange={e => setConsentForm(f => ({ ...f, collected_via: e.target.value }))}>
                  <option value="staff">Staff</option>
                  <option value="portal">Customer Portal</option>
                  <option value="form">Web Form</option>
                  <option value="import">Import</option>
                </select>
              </div>
              <div className="flex gap-3 pt-1">
                <button type="button" className="btn-secondary flex-1" onClick={() => setShowAddConsent(false)}>Cancel</button>
                <button type="submit" className="btn-primary flex-1">Record</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add DSAR modal */}
      {showAddDsar && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-background rounded-2xl shadow-xl w-full max-w-sm p-6 space-y-4">
            <h2 className="text-lg font-semibold">New Data Subject Request</h2>
            <form onSubmit={addDsar} className="space-y-3">
              <div>
                <label className="text-sm font-medium">Request Type</label>
                <select required className="input mt-1 w-full" value={dsarForm.request_type}
                  onChange={e => setDsarForm(f => ({ ...f, request_type: e.target.value }))}>
                  {DSAR_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">Requester Name *</label>
                <input required className="input mt-1 w-full"
                  value={dsarForm.requester_name} onChange={e => setDsarForm(f => ({ ...f, requester_name: e.target.value }))} />
              </div>
              <div>
                <label className="text-sm font-medium">Requester Email *</label>
                <input required type="email" className="input mt-1 w-full"
                  value={dsarForm.requester_email} onChange={e => setDsarForm(f => ({ ...f, requester_email: e.target.value }))} />
              </div>
              <div>
                <label className="text-sm font-medium">Description</label>
                <textarea className="input mt-1 w-full h-16 resize-none text-sm" placeholder="What data are they requesting…"
                  value={dsarForm.description} onChange={e => setDsarForm(f => ({ ...f, description: e.target.value }))} />
              </div>
              <div className="flex gap-3 pt-1">
                <button type="button" className="btn-secondary flex-1" onClick={() => setShowAddDsar(false)}>Cancel</button>
                <button type="submit" className="btn-primary flex-1">Submit</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
