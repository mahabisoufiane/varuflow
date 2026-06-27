"use client";

import { useState, useRef } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api-client";
import { toast } from "sonner";
import {
  Upload,
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  X,
} from "lucide-react";

interface ImportResult {
  rows_imported: number;
  errors: Array<{ row: number; message: string }>;
  total_rows: number;
}

type UploadStatus = "idle" | "uploading" | "done" | "error";

export default function ImportPage() {
  const t = useTranslations("inventory");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [result, setResult] = useState<ImportResult | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] ?? null;
    if (selected && !selected.name.endsWith(".csv")) {
      toast.error("Please select a CSV file.");
      return;
    }
    setFile(selected);
    setStatus("idle");
    setResult(null);
  };

  const handleUpload = async () => {
    if (!file) {
      toast.error("Please select a file first.");
      return;
    }
    try {
      setStatus("uploading");
      const data = await api.upload<ImportResult>(
        "/api/inventory/products/import",
        file
      );
      setResult(data);
      setStatus("done");
      toast.success(`Import complete: ${data.rows_imported} rows imported.`);
    } catch {
      setStatus("error");
      toast.error("Import failed. Please check your file and try again.");
    }
  };

  const reset = () => {
    setFile(null);
    setStatus("idle");
    setResult(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="vf-text-1 text-2xl font-semibold">
          Import Products
        </h1>
        <p className="vf-text-m mt-1">
          Bulk import products from a CSV file.
        </p>
      </div>

      <div className="vf-bg-card vf-border rounded-lg border p-6 space-y-6">
        {/* Upload area */}
        <div
          onClick={() => fileInputRef.current?.click()}
          className="vf-border flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-12 transition hover:border-blue-400 hover:bg-blue-50/50 dark:hover:bg-blue-900/10"
        >
          <Upload className="h-10 w-10 vf-text-m mb-3" />
          <p className="vf-text-1 font-medium">
            {file ? file.name : "Click to select a CSV file"}
          </p>
          <p className="vf-text-m mt-1 text-sm">
            {file
              ? `${(file.size / 1024).toFixed(1)} KB`
              : "Supported format: .csv"}
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            onChange={handleFileChange}
            className="hidden"
          />
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleUpload}
            disabled={!file || status === "uploading"}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {status === "uploading" ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <FileSpreadsheet className="h-4 w-4" />
            )}
            {status === "uploading" ? "Importing..." : "Import"}
          </button>
          {file && (
            <button
              onClick={reset}
              className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm vf-text-m hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              <X className="h-4 w-4" />
              Clear
            </button>
          )}
        </div>

        {/* Progress indicator */}
        {status === "uploading" && (
          <div className="space-y-2">
            <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
              <div className="h-full animate-pulse rounded-full bg-blue-500 w-2/3" />
            </div>
            <p className="vf-text-m text-sm">Processing your file...</p>
          </div>
        )}

        {/* Results */}
        {status === "done" && result && (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-emerald-500" />
              <span className="vf-text-1 font-medium">Import Complete</span>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="vf-border rounded-lg border p-4">
                <p className="vf-text-m text-sm">Total Rows</p>
                <p className="vf-text-1 text-2xl font-semibold">
                  {result.total_rows}
                </p>
              </div>
              <div className="vf-border rounded-lg border p-4">
                <p className="vf-text-m text-sm">Imported</p>
                <p className="text-2xl font-semibold text-emerald-600">
                  {result.rows_imported}
                </p>
              </div>
              <div className="vf-border rounded-lg border p-4">
                <p className="vf-text-m text-sm">Errors</p>
                <p
                  className={`text-2xl font-semibold ${
                    result.errors.length > 0 ? "text-red-500" : "vf-text-1"
                  }`}
                >
                  {result.errors.length}
                </p>
              </div>
            </div>

            {result.errors.length > 0 && (
              <div className="vf-border rounded-lg border overflow-hidden">
                <div className="flex items-center gap-2 px-4 py-3 bg-red-50 dark:bg-red-900/20">
                  <AlertTriangle className="h-4 w-4 text-red-500" />
                  <span className="text-sm font-medium text-red-700 dark:text-red-400">
                    Import Errors
                  </span>
                </div>
                <div className="divide-y vf-border max-h-60 overflow-y-auto">
                  {result.errors.map((err, i) => (
                    <div key={i} className="px-4 py-2 text-sm">
                      <span className="vf-text-m">Row {err.row}:</span>{" "}
                      <span className="vf-text-1">{err.message}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {status === "error" && (
          <div className="flex items-center gap-2 rounded-lg bg-red-50 dark:bg-red-900/20 px-4 py-3">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            <span className="text-sm text-red-700 dark:text-red-400">
              Import failed. Please verify your CSV format and try again.
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
