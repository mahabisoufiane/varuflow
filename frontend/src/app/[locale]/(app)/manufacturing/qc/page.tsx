"use client";

import { useEffect, useState } from "react";
import { ClipboardCheck, Plus, Loader2, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";

interface ChecklistItem {
  question: string;
  required: boolean;
}

interface Checklist {
  id: string;
  name: string;
  applies_to: string;
  items: ChecklistItem[];
  is_active: boolean;
}

interface Inspection {
  id: string;
  checklist_id: string;
  work_order_id: string | null;
  batch_id: string | null;
  status: string;
  inspector_name: string | null;
  inspected_at: string | null;
  created_at: string;
}

const STATUS_BADGE: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  passed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  pending: "statusPending",
  passed:  "statusPassed",
  failed:  "statusFailed",
};

export default function QcPage() {
  const [checklists, setChecklists] = useState<Checklist[]>([]);
  const [inspections, setInspections] = useState<Inspection[]>([]);
  const [selectedChecklist, setSelectedChecklist] = useState<Checklist | null>(null);
  const [loading, setLoading] = useState(true);
  const [showChecklistForm, setShowChecklistForm] = useState(false);
  const [checklistForm, setChecklistForm] = useState({ name: "", applies_to: "work_order" });
  const [newItem, setNewItem] = useState({ question: "", required: true });
  const [showInspectionForm, setShowInspectionForm] = useState(false);
  const [inspectionForm, setInspectionForm] = useState({ checklist_id: "", work_order_id: "", batch_id: "", inspector_name: "" });
  const [submittingId, setSubmittingId] = useState<string | null>(null);
  const [submitForm, setSubmitForm] = useState<{ status: string; results: Record<string, string> }>({ status: "passed", results: {} });

  async function load() {
    try {
      const [clList, inspList] = await Promise.all([
        api.get("/api/manufacturing/qc/checklists"),
        api.get("/api/manufacturing/qc/inspections"),
      ]);
      setChecklists(clList);
      setInspections(inspList);
    } catch {
      toast.error("Failed to load QC data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function createChecklist() {
    if (!checklistForm.name) { toast.error("Enter a name"); return; }
    try {
      const created = await api.post("/api/manufacturing/qc/checklists", { ...checklistForm, items: [] });
      setChecklists((c) => [created, ...c]);
      setShowChecklistForm(false);
      setSelectedChecklist(created);
      toast.success("Checklist created");
    } catch { toast.error("Failed to create checklist"); }
  }

  async function addItem() {
    if (!selectedChecklist || !newItem.question) return;
    const updated = { items: [...selectedChecklist.items, newItem] };
    try {
      const saved = await api.patch(`/api/manufacturing/qc/checklists/${selectedChecklist.id}`, updated);
      setChecklists((c) => c.map((x) => x.id === selectedChecklist.id ? { ...x, ...saved } : x));
      setSelectedChecklist((s) => s ? { ...s, ...saved } : null);
      setNewItem({ question: "", required: true });
      toast.success("Item added");
    } catch { toast.error("Failed to add item"); }
  }

  async function removeItem(idx: number) {
    if (!selectedChecklist) return;
    const items = selectedChecklist.items.filter((_, i) => i !== idx);
    try {
      const saved = await api.patch(`/api/manufacturing/qc/checklists/${selectedChecklist.id}`, { items });
      setChecklists((c) => c.map((x) => x.id === selectedChecklist.id ? { ...x, ...saved } : x));
      setSelectedChecklist((s) => s ? { ...s, ...saved } : null);
    } catch { toast.error("Failed to remove item"); }
  }

  async function deleteChecklist(id: string) {
    try {
      await api.delete(`/api/manufacturing/qc/checklists/${id}`);
      setChecklists((c) => c.filter((x) => x.id !== id));
      if (selectedChecklist?.id === id) setSelectedChecklist(null);
      toast.success("Checklist deleted");
    } catch { toast.error("Failed to delete checklist"); }
  }

  async function createInspection() {
    if (!inspectionForm.checklist_id) { toast.error("Select checklist"); return; }
    try {
      const body: any = { checklist_id: inspectionForm.checklist_id, inspector_name: inspectionForm.inspector_name || undefined };
      if (inspectionForm.work_order_id) body.work_order_id = inspectionForm.work_order_id;
      if (inspectionForm.batch_id) body.batch_id = inspectionForm.batch_id;
      const created = await api.post("/api/manufacturing/qc/inspections", body);
      setInspections((i) => [created, ...i]);
      setShowInspectionForm(false);
      toast.success("Inspection created");
    } catch { toast.error("Failed to create inspection"); }
  }

  async function submitInspection(id: string) {
    try {
      const updated = await api.patch(`/api/manufacturing/qc/inspections/${id}`, submitForm);
      setInspections((i) => i.map((x) => x.id === id ? { ...x, ...updated } : x));
      setSubmittingId(null);
      toast.success(`Inspection ${submitForm.status}`);
    } catch { toast.error("Failed to submit inspection"); }
  }

  const checklistMap = Object.fromEntries(checklists.map((c) => [c.id, c]));

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center gap-2 mb-6">
        <ClipboardCheck className="w-6 h-6" />
        <h1 className="text-2xl font-semibold">Quality Control</h1>
      </div>

      <div className="grid grid-cols-12 gap-6 mb-8">
        {/* Checklist list */}
        <div className="col-span-3 border rounded-lg p-3">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold">Checklists</h3>
            <button onClick={() => setShowChecklistForm((x) => !x)} className="p-1 hover:bg-accent rounded"><Plus className="w-4 h-4" /></button>
          </div>
          {showChecklistForm && (
            <div className="space-y-2 mb-3 border-b pb-3">
              <input className="border rounded px-2 py-1 text-xs w-full" placeholder="Name" value={checklistForm.name} onChange={(e) => setChecklistForm((f) => ({ ...f, name: e.target.value }))} />
              <select className="border rounded px-2 py-1 text-xs w-full" value={checklistForm.applies_to} onChange={(e) => setChecklistForm((f) => ({ ...f, applies_to: e.target.value }))}>
                <option value="work_order">Work Order</option>
                <option value="batch">Batch</option>
              </select>
              <div className="flex gap-1">
                <button onClick={createChecklist} className="bg-primary text-primary-foreground rounded px-2 py-1 text-xs">Create</button>
                <button onClick={() => setShowChecklistForm(false)} className="border rounded px-2 py-1 text-xs">Cancel</button>
              </div>
            </div>
          )}
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : (
            <div className="space-y-1">
              {checklists.map((c) => (
                <button key={c.id} onClick={() => setSelectedChecklist(c)} className={`w-full text-left p-2 rounded text-xs hover:bg-accent ${selectedChecklist?.id === c.id ? "bg-accent" : ""}`}>
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{c.name}</span>
                    <span className={`text-[10px] px-1.5 rounded-full ${c.applies_to === "work_order" ? "bg-blue-100 text-blue-800" : "bg-orange-100 text-orange-800"}`}>{c.applies_to === "work_order" ? "WO" : "Batch"}</span>
                  </div>
                  <p className="text-muted-foreground">{c.items.length} items</p>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Checklist editor */}
        <div className="col-span-9 border rounded-lg p-4">
          {selectedChecklist ? (
            <>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-semibold">{selectedChecklist.name}</h3>
                  <p className="text-xs text-muted-foreground">Applies to: {selectedChecklist.applies_to === "work_order" ? "Work Orders" : "Batches"}</p>
                </div>
                <button onClick={() => deleteChecklist(selectedChecklist.id)} className="text-destructive text-xs border rounded px-2 py-1 hover:bg-red-50">Delete</button>
              </div>
              <div className="space-y-1 mb-4">
                {selectedChecklist.items.map((item, i) => (
                  <div key={i} className="flex items-center justify-between border rounded px-3 py-2 text-sm">
                    <span>{item.question} {item.required && <span className="text-red-500">*</span>}</span>
                    <button onClick={() => removeItem(i)} className="text-muted-foreground hover:text-destructive ml-2"><Trash2 className="w-3 h-3" /></button>
                  </div>
                ))}
              </div>
              <div className="flex gap-2 border-t pt-3">
                <input className="border rounded px-2 py-1.5 text-sm flex-1" placeholder="New question…" value={newItem.question} onChange={(e) => setNewItem((f) => ({ ...f, question: e.target.value }))} onKeyDown={(e) => e.key === "Enter" && addItem()} />
                <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={newItem.required} onChange={(e) => setNewItem((f) => ({ ...f, required: e.target.checked }))} /> Required</label>
                <button onClick={addItem} className="bg-primary text-primary-foreground rounded px-3 py-1.5 text-sm">Add</button>
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">Select a checklist to edit its questions.</p>
          )}
        </div>
      </div>

      {/* Inspection log */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold">Inspection Log</h3>
          <button onClick={() => setShowInspectionForm((x) => !x)} className="flex items-center gap-1.5 text-sm border rounded px-3 py-1.5 hover:bg-accent">
            <Plus className="w-4 h-4" /> New Inspection
          </button>
        </div>

        {showInspectionForm && (
          <div className="border rounded p-4 mb-4 grid grid-cols-2 gap-3 max-w-lg">
            <div>
              <label className="text-xs font-medium text-muted-foreground">Checklist</label>
              <select className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={inspectionForm.checklist_id} onChange={(e) => setInspectionForm((f) => ({ ...f, checklist_id: e.target.value }))}>
                <option value="">— select —</option>
                {checklists.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Inspector</label>
              <input className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={inspectionForm.inspector_name} onChange={(e) => setInspectionForm((f) => ({ ...f, inspector_name: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Work Order ID (optional)</label>
              <input className="border rounded px-2 py-1.5 text-sm w-full mt-1" placeholder="UUID" value={inspectionForm.work_order_id} onChange={(e) => setInspectionForm((f) => ({ ...f, work_order_id: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Batch ID (optional)</label>
              <input className="border rounded px-2 py-1.5 text-sm w-full mt-1" placeholder="UUID" value={inspectionForm.batch_id} onChange={(e) => setInspectionForm((f) => ({ ...f, batch_id: e.target.value }))} />
            </div>
            <div className="col-span-2 flex gap-2">
              <button onClick={createInspection} className="bg-primary text-primary-foreground rounded px-3 py-1.5 text-sm">Create</button>
              <button onClick={() => setShowInspectionForm(false)} className="border rounded px-3 py-1.5 text-sm">Cancel</button>
            </div>
          </div>
        )}

        {submittingId && (
          <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
            <div className="bg-background rounded-lg p-6 max-w-sm w-full shadow-lg">
              <h3 className="font-semibold mb-3">Submit Inspection Result</h3>
              <div className="space-y-3">
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Result</label>
                  <select className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={submitForm.status} onChange={(e) => setSubmitForm((f) => ({ ...f, status: e.target.value }))}>
                    <option value="passed">Passed</option>
                    <option value="failed">Failed</option>
                  </select>
                </div>
                {checklistMap[inspections.find((i) => i.id === submittingId)?.checklist_id ?? ""]?.items.map((item, idx) => (
                  <div key={idx}>
                    <label className="text-xs font-medium text-muted-foreground">{item.question}{item.required && " *"}</label>
                    <input className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={submitForm.results[item.question] ?? ""} onChange={(e) => setSubmitForm((f) => ({ ...f, results: { ...f.results, [item.question]: e.target.value } }))} />
                  </div>
                ))}
              </div>
              <div className="flex gap-2 justify-end mt-4">
                <button onClick={() => setSubmittingId(null)} className="border rounded px-3 py-1.5 text-sm">Cancel</button>
                <button onClick={() => submitInspection(submittingId)} className={`rounded px-3 py-1.5 text-sm text-white ${submitForm.status === "passed" ? "bg-green-600" : "bg-red-600"}`}>
                  Mark {submitForm.status}
                </button>
              </div>
            </div>
          </div>
        )}

        {inspections.length === 0 ? (
          <p className="text-sm text-muted-foreground">No inspections yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="border-b text-left text-muted-foreground"><th className="py-2 pr-4 font-medium">Checklist</th><th className="py-2 pr-4 font-medium">Reference</th><th className="py-2 pr-4 font-medium">Inspector</th><th className="py-2 pr-4 font-medium">Status</th><th className="py-2 pr-4 font-medium">Date</th><th /></tr></thead>
            <tbody className="divide-y">
              {inspections.map((insp) => (
                <tr key={insp.id}>
                  <td className="py-2 pr-4">{checklistMap[insp.checklist_id]?.name ?? insp.checklist_id.slice(0, 8)}</td>
                  <td className="py-2 pr-4 text-muted-foreground text-xs">
                    {insp.work_order_id ? `WO: ${insp.work_order_id.slice(0, 8)}` : insp.batch_id ? `Batch: ${insp.batch_id.slice(0, 8)}` : "—"}
                  </td>
                  <td className="py-2 pr-4">{insp.inspector_name ?? "—"}</td>
                  <td className="py-2 pr-4">
                    <span className={styles[STATUS_MODULE[insp.status] ?? "statusPending"]}>{insp.status}</span>
                  </td>
                  <td className="py-2 pr-4 text-xs text-muted-foreground">{insp.inspected_at ? new Date(insp.inspected_at).toLocaleDateString() : "—"}</td>
                  <td className="py-2">
                    {insp.status === "pending" && (
                      <button onClick={() => { setSubmittingId(insp.id); setSubmitForm({ status: "passed", results: {} }); }} className="text-xs border rounded px-2 py-0.5 hover:bg-accent">Submit</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
