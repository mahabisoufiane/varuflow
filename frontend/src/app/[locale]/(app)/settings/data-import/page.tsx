"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import {
  Upload, ChevronRight, CheckCircle2, XCircle, RefreshCw, Trash2,
  AlertTriangle, ArrowLeft, FileSpreadsheet,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";

type WizardStep = "source" | "upload" | "mapping" | "validate" | "execute" | "done";

interface UploadPreview {
  job_id: string;
  headers: string[];
  preview_rows: string[][];
  total_rows: number;
  suggested_mapping: Record<string, string>;
}

interface ImportJob {
  id: string;
  import_type: string;
  status: string;
  filename: string | null;
  total_rows: number | null;
  imported_rows: number | null;
  failed_rows: number | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

const SOURCE_SYSTEMS = [
  { id: "quickbooks", label: "QuickBooks", logo: "🔵" },
  { id: "xero",       label: "Xero",       logo: "🔹" },
  { id: "fortnox",    label: "Fortnox",    logo: "🇸🇪" },
  { id: "visma",      label: "Visma",      logo: "🟦" },
  { id: "sage",       label: "Sage",       logo: "🟩" },
  { id: "csv",        label: "Generic CSV/XLSX", logo: "📄" },
];

const IMPORT_TYPES = [
  { id: "customers",  label: "Customers"  },
  { id: "products",   label: "Products"   },
  { id: "suppliers",  label: "Suppliers"  },
  { id: "invoices",   label: "Invoices"   },
];

const STATUS_COLORS: Record<string, string> = {
  pending:    "bg-gray-100 text-gray-600",
  processing: "bg-blue-100 text-blue-700",
  done:       "bg-green-100 text-green-700",
  failed:     "bg-red-100 text-red-700",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  pending:    "statusPending",
  processing: "statusProcessing",
  done:       "statusDone",
  failed:     "statusFailed",
};

export default function DataImportPage() {
  const router = useRouter();
  const supabase = createClient();
  const fileRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState<WizardStep>("source");
  const [sourceSystem, setSourceSystem] = useState("");
  const [importType, setImportType] = useState("customers");
  const [preview, setPreview] = useState<UploadPreview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [validationErrors, setValidationErrors] = useState<{ row: number; field: string; message: string }[]>([]);
  const [validRows, setValidRows] = useState(0);
  const [jobs, setJobs] = useState<ImportJob[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [finalJob, setFinalJob] = useState<ImportJob | null>(null);

  async function getToken() {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token ?? null;
  }
  function apiUrl(path: string) { return `${process.env.NEXT_PUBLIC_API_URL}${path}`; }

  async function loadJobs() {
    setLoadingJobs(true);
    try {
      const token = await getToken();
      if (!token) { router.push("/auth/login"); return; }
      const res = await fetch(apiUrl("/api/data-import/jobs?limit=20"), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) { router.push("/auth/login"); return; }
      if (res.ok) {
        const data = await res.json();
        setJobs(data.jobs ?? []);
      }
    } catch {
      // silent — jobs list is supplementary
    } finally {
      setLoadingJobs(false);
    }
  }

  useEffect(() => { loadJobs(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setActionLoading(true);
    try {
      const token = await getToken();
      if (!token) { router.push("/auth/login"); return; }
      const form = new FormData();
      form.append("file", file);
      form.append("import_type", importType);
      form.append("source_system", sourceSystem || "csv");

      const res = await fetch(apiUrl("/api/data-import/upload"), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (res.status === 401) { router.push("/auth/login"); return; }
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Upload failed");
        return;
      }
      const data: UploadPreview = await res.json();
      setPreview(data);
      setMapping(data.suggested_mapping ?? {});
      setStep("mapping");
    } catch {
      toast.error("Upload failed. Please try again.");
    } finally {
      setActionLoading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function handleSaveMapping() {
    if (!preview) return;
    setActionLoading(true);
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/data-import/jobs/${preview.job_id}/mapping`), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ column_mapping: mapping }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to save mapping");
        return;
      }
      setStep("validate");
      await handleValidate();
    } catch {
      toast.error("Something went wrong. Please try again.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleValidate() {
    if (!preview) return;
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/data-import/jobs/${preview.job_id}/validate`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;
      const data = await res.json();
      setValidationErrors(data.errors ?? []);
      setValidRows(data.valid_rows ?? 0);
    } catch {}
  }

  async function handleExecute() {
    if (!preview) return;
    setActionLoading(true);
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/data-import/jobs/${preview.job_id}/execute`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Import failed");
        return;
      }
      const job: ImportJob = await res.json();
      setFinalJob(job);
      setStep("done");
      await loadJobs();
    } catch {
      toast.error("Something went wrong. Please try again.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDeleteJob(jobId: string) {
    try {
      const token = await getToken();
      if (!token) return;
      await fetch(apiUrl(`/api/data-import/jobs/${jobId}`), {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      await loadJobs();
    } catch {}
  }

  function reset() {
    setStep("source");
    setSourceSystem("");
    setPreview(null);
    setMapping({});
    setValidationErrors([]);
    setValidRows(0);
    setFinalJob(null);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5" /> Data Import
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Import customers, products, suppliers, and invoices from CSV or your existing accounting system.
          </p>
        </div>
        {step !== "source" && (
          <Button variant="outline" size="sm" onClick={reset}>
            <ArrowLeft className="h-4 w-4 mr-2" /> Start Over
          </Button>
        )}
      </div>

      {/* ── Step indicator ── */}
      <div className="flex items-center gap-1 text-xs text-muted-foreground">
        {(["source","upload","mapping","validate","execute","done"] as WizardStep[]).map((s, i) => (
          <span key={s} className="flex items-center gap-1">
            <span className={`font-medium ${s === step ? "text-[#1a2332]" : ""}`}>
              {["Source","Upload","Mapping","Validate","Execute","Done"][i]}
            </span>
            {i < 5 && <ChevronRight className="h-3 w-3" />}
          </span>
        ))}
      </div>

      {/* ── Step: Source ── */}
      {step === "source" && (
        <div className="rounded-xl border bg-white p-6 shadow-sm space-y-5">
          <h2 className="text-base font-semibold text-gray-900">Select Source System</h2>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {SOURCE_SYSTEMS.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => setSourceSystem(s.id)}
                className={`flex flex-col items-center gap-2 rounded-lg border p-4 text-sm font-medium transition-colors ${
                  sourceSystem === s.id
                    ? "border-[#1a2332] bg-[#1a2332]/5 text-[#1a2332]"
                    : "border-gray-200 hover:bg-gray-50 text-gray-700"
                }`}
              >
                <span className="text-2xl">{s.logo}</span>
                {s.label}
              </button>
            ))}
          </div>

          <div className="space-y-2">
            <h3 className="text-sm font-medium text-gray-900">What to import</h3>
            <div className="grid grid-cols-2 gap-2">
              {IMPORT_TYPES.map((t) => (
                <label key={t.id} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="import_type"
                    value={t.id}
                    checked={importType === t.id}
                    onChange={() => setImportType(t.id)}
                    className="accent-[#1a2332]"
                  />
                  <span className="text-sm text-gray-700">{t.label}</span>
                </label>
              ))}
            </div>
          </div>

          <Button
            className="w-full bg-[#1a2332] hover:bg-[#2a3342] text-white"
            disabled={!sourceSystem}
            onClick={() => setStep("upload")}
          >
            Continue
          </Button>
        </div>
      )}

      {/* ── Step: Upload ── */}
      {step === "upload" && (
        <div className="rounded-xl border bg-white p-6 shadow-sm space-y-5">
          <h2 className="text-base font-semibold text-gray-900">Upload File</h2>
          <p className="text-sm text-muted-foreground">
            Upload a CSV or XLSX export from{" "}
            {SOURCE_SYSTEMS.find((s) => s.id === sourceSystem)?.label ?? "your source system"}.
            The first row must be a header row.
          </p>

          <div
            className="flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-gray-200 px-6 py-12 text-center hover:bg-gray-50 transition-colors cursor-pointer"
            onClick={() => fileRef.current?.click()}
          >
            <Upload className="h-8 w-8 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium text-gray-700">Click to choose file</p>
              <p className="text-xs text-muted-foreground">.csv, .xlsx — max 10 MB</p>
            </div>
          </div>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            className="hidden"
            onChange={handleFileUpload}
          />

          {actionLoading && (
            <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
              <RefreshCw className="h-4 w-4 animate-spin" />
              Uploading and parsing…
            </div>
          )}

          <Button variant="outline" className="w-full" onClick={() => setStep("source")}>
            <ArrowLeft className="h-4 w-4 mr-2" /> Back
          </Button>
        </div>
      )}

      {/* ── Step: Mapping ── */}
      {step === "mapping" && preview && (
        <div className="rounded-xl border bg-white p-6 shadow-sm space-y-5">
          <h2 className="text-base font-semibold text-gray-900">Column Mapping</h2>
          <p className="text-sm text-muted-foreground">
            Detected {preview.total_rows} rows with {preview.headers.length} columns.
            Map each column to your destination field.
          </p>

          {/* Preview table */}
          <div className="overflow-x-auto rounded-lg border">
            <table className="min-w-full text-xs">
              <thead className="bg-gray-50">
                <tr>
                  {preview.headers.map((h) => (
                    <th key={h} className="px-3 py-2 text-left font-medium text-gray-600">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.preview_rows.slice(0, 3).map((row, i) => (
                  <tr key={i} className="border-t">
                    {row.map((cell, j) => (
                      <td key={j} className="px-3 py-2 text-gray-700">{cell || "—"}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mapping selects */}
          <div className="space-y-3">
            {preview.headers.map((h) => (
              <div key={h} className="flex items-center gap-3">
                <span className="w-40 flex-shrink-0 text-sm font-medium text-gray-700 truncate">{h}</span>
                <ChevronRight className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                <select
                  value={mapping[h] ?? ""}
                  onChange={(e) => setMapping((m) => ({ ...m, [h]: e.target.value }))}
                  className="flex-1 rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:border-[#1a2332] focus:ring-[#1a2332]"
                >
                  <option value="">(skip)</option>
                  <option value="company_name">company_name</option>
                  <option value="email">email</option>
                  <option value="org_number">org_number</option>
                  <option value="phone">phone</option>
                  <option value="address">address</option>
                  <option value="name">name</option>
                  <option value="sku">sku</option>
                  <option value="sell_price">sell_price</option>
                  <option value="purchase_price">purchase_price</option>
                  <option value="tax_rate">tax_rate</option>
                  <option value="unit">unit</option>
                  <option value="description">description</option>
                  <option value="invoice_number">invoice_number</option>
                  <option value="issue_date">issue_date</option>
                  <option value="due_date">due_date</option>
                  <option value="total_amount">total_amount</option>
                </select>
              </div>
            ))}
          </div>

          <div className="flex gap-3">
            <Button variant="outline" className="flex-1" onClick={() => setStep("upload")}>
              <ArrowLeft className="h-4 w-4 mr-2" /> Back
            </Button>
            <Button
              className="flex-1 bg-[#1a2332] hover:bg-[#2a3342] text-white"
              disabled={actionLoading}
              onClick={handleSaveMapping}
            >
              {actionLoading
                ? <><RefreshCw className="h-4 w-4 mr-2 animate-spin" /> Validating…</>
                : "Validate Data"}
            </Button>
          </div>
        </div>
      )}

      {/* ── Step: Validate ── */}
      {step === "validate" && preview && (
        <div className="rounded-xl border bg-white p-6 shadow-sm space-y-5">
          <h2 className="text-base font-semibold text-gray-900">Validation Results</h2>

          <div className="flex gap-4">
            <div className="flex-1 rounded-lg bg-green-50 border border-green-200 px-4 py-3 text-center">
              <p className="text-2xl font-bold text-green-700">{validRows}</p>
              <p className="text-xs text-green-600">Valid rows</p>
            </div>
            <div className="flex-1 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-center">
              <p className="text-2xl font-bold text-red-700">{validationErrors.length}</p>
              <p className="text-xs text-red-600">Errors</p>
            </div>
          </div>

          {validationErrors.length > 0 && (
            <div className="space-y-2 max-h-48 overflow-y-auto rounded-lg border p-3">
              {validationErrors.slice(0, 50).map((e, i) => (
                <div key={i} className="flex items-start gap-2 text-sm">
                  <AlertTriangle className="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" />
                  <span className="text-gray-700">
                    Row {e.row} — <strong>{e.field}</strong>: {e.message}
                  </span>
                </div>
              ))}
              {validationErrors.length > 50 && (
                <p className="text-xs text-muted-foreground text-center">
                  …and {validationErrors.length - 50} more errors
                </p>
              )}
            </div>
          )}

          {validationErrors.length > 0 && (
            <div className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3">
              <p className="text-sm text-amber-800">
                Rows with errors will be skipped. You can still import {validRows} valid rows.
              </p>
            </div>
          )}

          <div className="flex gap-3">
            <Button variant="outline" className="flex-1" onClick={() => setStep("mapping")}>
              <ArrowLeft className="h-4 w-4 mr-2" /> Back
            </Button>
            <Button
              className="flex-1 bg-[#1a2332] hover:bg-[#2a3342] text-white"
              disabled={validRows === 0 || actionLoading}
              onClick={() => { setStep("execute"); handleExecute(); }}
            >
              {`Import ${validRows} rows`}
            </Button>
          </div>
        </div>
      )}

      {/* ── Step: Execute (progress) ── */}
      {step === "execute" && (
        <div className="rounded-xl border bg-white p-8 shadow-sm space-y-4 text-center">
          <RefreshCw className="h-8 w-8 animate-spin mx-auto text-[#1a2332]" />
          <p className="text-sm font-medium text-gray-700">Importing data…</p>
          <p className="text-xs text-muted-foreground">This may take a moment for large files.</p>
        </div>
      )}

      {/* ── Step: Done ── */}
      {step === "done" && finalJob && (
        <div className="rounded-xl border bg-white p-8 shadow-sm space-y-5 text-center">
          {finalJob.status === "done" ? (
            <CheckCircle2 className="h-12 w-12 text-green-500 mx-auto" />
          ) : (
            <XCircle className="h-12 w-12 text-red-500 mx-auto" />
          )}

          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              {finalJob.status === "done" ? "Import Complete" : "Import Failed"}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {finalJob.status === "done"
                ? `${finalJob.imported_rows ?? 0} rows imported, ${finalJob.failed_rows ?? 0} skipped.`
                : finalJob.error_message ?? "An unexpected error occurred."}
            </p>
          </div>

          <div className="flex gap-3 justify-center">
            <Button variant="outline" onClick={reset}>Import Another File</Button>
            {finalJob.status === "done" && (
              <Button className="bg-[#1a2332] hover:bg-[#2a3342] text-white" onClick={() => router.push("/dashboard")}>
                Go to Dashboard
              </Button>
            )}
          </div>
        </div>
      )}

      {/* ── Past import jobs ── */}
      {jobs.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-gray-900">Import History</h2>
          <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
            {loadingJobs
              ? <div className="px-5 py-4 text-sm text-muted-foreground">Loading…</div>
              : jobs.map((job) => (
                <div key={job.id} className="flex items-center gap-3 px-5 py-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {job.filename ?? job.import_type}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {job.import_type} · {job.imported_rows ?? 0} rows
                      {job.failed_rows ? ` · ${job.failed_rows} failed` : ""}
                      {" · "}{new Date(job.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <span className={styles[STATUS_MODULE[job.status] ?? "statusPending"]}>
                    {job.status}
                  </span>
                  {job.status === "pending" && (
                    <button
                      type="button"
                      onClick={() => handleDeleteJob(job.id)}
                      className="text-muted-foreground hover:text-red-600 transition-colors"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
