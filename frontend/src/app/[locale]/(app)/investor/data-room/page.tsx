"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { PlusCircle, RefreshCw, Trash2, Copy, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface Folder {
  id: string;
  name: string;
}

interface Document {
  id: string;
  name: string;
  mime_type: string | null;
  file_url: string;
  file_size: number | null;
  created_at: string;
}

interface ShareLink {
  id: string;
  label: string;
  token: string;
  expires_at: string | null;
  view_count: number;
  folder_ids: string[];
}

function fmtSize(bytes: number | null | undefined) {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DataRoomPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [folders, setFolders] = useState<Folder[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<Folder | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [shares, setShares] = useState<ShareLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [docsLoading, setDocsLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [tab, setTab] = useState<"files" | "shares">("files");

  const [newFolderName, setNewFolderName] = useState("");
  const [showFolderForm, setShowFolderForm] = useState(false);

  const [showDocForm, setShowDocForm] = useState(false);
  const [docForm, setDocForm] = useState({ name: "", file_url: "", file_size: "", mime_type: "" });

  const [showShareForm, setShowShareForm] = useState(false);
  const [shareForm, setShareForm] = useState({ label: "", folder_ids: [] as string[], expires_at: "" });

  async function getToken() {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token ?? null;
  }
  function apiUrl(p: string) { return `${process.env.NEXT_PUBLIC_API_URL}${p}`; }

  async function load() {
    setLoading(true);
    try {
      const token = await getToken();
      if (!token) { router.push(`/${locale}/auth/login`); return; }
      const [fRes, sRes] = await Promise.all([
        fetch(apiUrl("/api/data-room/folders"), { headers: { Authorization: `Bearer ${token}` } }),
        fetch(apiUrl("/api/data-room/shares"), { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (fRes.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (fRes.ok) setFolders(await fRes.json());
      if (sRes.ok) setShares(await sRes.json());
    } catch {
      toast.error("Failed to load data room");
    } finally {
      setLoading(false);
    }
  }

  async function loadDocs(folderId: string) {
    setDocsLoading(true);
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/data-room/folders/${folderId}/documents`), { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) setDocuments(await res.json());
    } catch {
      toast.error("Failed to load documents");
    } finally {
      setDocsLoading(false);
    }
  }

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function createFolder() {
    if (!newFolderName.trim()) { toast.error("Folder name is required"); return; }
    setActionLoading("folder_create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/data-room/folders"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name: newFolderName }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to create"); return; }
      toast.success("Folder created");
      setShowFolderForm(false);
      setNewFolderName("");
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function addDocument() {
    if (!docForm.name.trim() || !docForm.file_url.trim()) { toast.error("Name and URL are required"); return; }
    if (!selectedFolder) return;
    setActionLoading("doc_create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/data-room/folders/${selectedFolder.id}/documents`), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          name: docForm.name,
          file_url: docForm.file_url,
          file_size: docForm.file_size ? parseInt(docForm.file_size) : null,
          mime_type: docForm.mime_type || null,
        }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to add"); return; }
      toast.success("Document added");
      setShowDocForm(false);
      setDocForm({ name: "", file_url: "", file_size: "", mime_type: "" });
      await loadDocs(selectedFolder.id);
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function deleteDocument(docId: string) {
    if (!selectedFolder) return;
    setActionLoading(docId + "_del");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/data-room/documents/${docId}`), {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to delete"); return; }
      toast.success("Document deleted");
      await loadDocs(selectedFolder.id);
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function createShare() {
    if (!shareForm.label.trim()) { toast.error("Label is required"); return; }
    setActionLoading("share_create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/data-room/shares"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          label: shareForm.label,
          folder_ids: shareForm.folder_ids,
          expires_at: shareForm.expires_at || null,
        }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to create share"); return; }
      toast.success("Share link created");
      setShowShareForm(false);
      setShareForm({ label: "", folder_ids: [], expires_at: "" });
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function revokeShare(shareId: string) {
    setActionLoading(shareId + "_revoke");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/data-room/shares/${shareId}`), {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to revoke"); return; }
      toast.success("Share link revoked");
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  function selectFolder(f: Folder) {
    setSelectedFolder(f);
    loadDocs(f.id);
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Data Room</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Secure document sharing for fundraising and M&A.</p>
      </div>

      <div className="flex items-center gap-1 border-b">
        {[{ key: "files" as const, label: "Files" }, { key: "shares" as const, label: "Share Links" }].map((t) => (
          <button key={t.key} type="button" onClick={() => setTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${tab === t.key ? "border-[#1a2332] text-[#1a2332]" : "border-transparent text-muted-foreground hover:text-gray-700"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-12"><RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" /></div>
      ) : tab === "files" ? (
        <div className="flex gap-4 min-h-96">
          {/* Folder list */}
          <div className="w-56 flex-shrink-0 space-y-2">
            <div className="flex items-center justify-between mb-1">
              <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Folders</p>
              <button type="button" onClick={() => setShowFolderForm(true)}
                className="rounded-md p-1 hover:bg-gray-100">
                <PlusCircle className="h-4 w-4 text-[#1a2332]" />
              </button>
            </div>
            {showFolderForm && (
              <div className="space-y-2">
                <input value={newFolderName} onChange={(e) => setNewFolderName(e.target.value)}
                  placeholder="Folder name"
                  className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                <div className="flex gap-1">
                  <Button size="sm" disabled={actionLoading === "folder_create"} onClick={createFolder}
                    className="bg-[#1a2332] hover:bg-[#2a3342] text-white text-xs px-2 py-1 h-auto">
                    Add
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setShowFolderForm(false)} className="text-xs px-2 py-1 h-auto">
                    <X className="h-3 w-3" />
                  </Button>
                </div>
              </div>
            )}
            <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
              {folders.length === 0 ? (
                <p className="px-3 py-3 text-xs text-gray-500">No folders</p>
              ) : folders.map((f) => (
                <button key={f.id} type="button"
                  onClick={() => selectFolder(f)}
                  className={`w-full text-left px-3 py-2.5 text-sm transition-colors ${selectedFolder?.id === f.id ? "bg-[#1a2332]/5 font-medium text-[#1a2332]" : "text-gray-700 hover:bg-gray-50"}`}>
                  {f.name}
                </button>
              ))}
            </div>
          </div>

          {/* Document panel */}
          <div className="flex-1 space-y-3">
            {selectedFolder ? (
              <>
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-gray-900">{selectedFolder.name}</p>
                  <Button size="sm" onClick={() => setShowDocForm(true)}
                    className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
                    <PlusCircle className="h-3 w-3" /> Add Document
                  </Button>
                </div>
                {showDocForm && (
                  <div className="rounded-xl border border-[#1a2332]/20 bg-white p-4 shadow-sm space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1 col-span-2">
                        <label className="text-xs font-medium text-gray-700">Name *</label>
                        <input value={docForm.name} onChange={(e) => setDocForm((f) => ({ ...f, name: e.target.value }))}
                          className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                      </div>
                      <div className="space-y-1 col-span-2">
                        <label className="text-xs font-medium text-gray-700">File URL *</label>
                        <input value={docForm.file_url} onChange={(e) => setDocForm((f) => ({ ...f, file_url: e.target.value }))}
                          placeholder="https://..."
                          className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs font-medium text-gray-700">MIME Type</label>
                        <input value={docForm.mime_type} onChange={(e) => setDocForm((f) => ({ ...f, mime_type: e.target.value }))}
                          placeholder="application/pdf"
                          className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs font-medium text-gray-700">File Size (bytes)</label>
                        <input type="number" value={docForm.file_size} onChange={(e) => setDocForm((f) => ({ ...f, file_size: e.target.value }))}
                          className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" onClick={() => setShowDocForm(false)}>Cancel</Button>
                      <Button size="sm" disabled={actionLoading === "doc_create"} onClick={addDocument}
                        className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
                        {actionLoading === "doc_create" ? "Adding…" : "Add Document"}
                      </Button>
                    </div>
                  </div>
                )}
                {docsLoading ? (
                  <div className="py-8 text-center"><RefreshCw className="h-5 w-5 animate-spin mx-auto text-muted-foreground" /></div>
                ) : (
                  <div className="rounded-xl border bg-white shadow-sm overflow-hidden">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 border-b">
                        <tr>
                          <th className="px-4 py-3 text-left font-medium text-gray-700">Name</th>
                          <th className="px-4 py-3 text-left font-medium text-gray-700">Type</th>
                          <th className="px-4 py-3 text-right font-medium text-gray-700">Size</th>
                          <th className="px-4 py-3 text-right font-medium text-gray-700">Added</th>
                          <th className="px-4 py-3 w-8" />
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {documents.length === 0 ? (
                          <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-500">No documents in this folder</td></tr>
                        ) : documents.map((d) => (
                          <tr key={d.id}>
                            <td className="px-4 py-3 text-gray-900 font-medium">{d.name}</td>
                            <td className="px-4 py-3">
                              {d.mime_type && (
                                <span className="rounded-full bg-blue-50 text-blue-700 px-2 py-0.5 text-xs">{d.mime_type}</span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-right text-gray-600 text-xs">{fmtSize(d.file_size)}</td>
                            <td className="px-4 py-3 text-right text-gray-500 text-xs">{new Date(d.created_at).toLocaleDateString()}</td>
                            <td className="px-4 py-3 text-right">
                              <button type="button" disabled={actionLoading === d.id + "_del"}
                                onClick={() => deleteDocument(d.id)}
                                className="text-red-400 hover:text-red-600 disabled:opacity-50">
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            ) : (
              <div className="flex items-center justify-center h-48 text-sm text-gray-400">
                Select a folder to view its documents
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Shares tab */
        <div className="space-y-4">
          <div className="flex justify-end">
            <Button onClick={() => setShowShareForm(true)} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
              <PlusCircle className="h-4 w-4" /> Create Share Link
            </Button>
          </div>
          {showShareForm && (
            <div className="rounded-xl border border-[#1a2332]/20 bg-white p-5 shadow-sm space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1 col-span-2">
                  <label className="text-xs font-medium text-gray-700">Label *</label>
                  <input value={shareForm.label} onChange={(e) => setShareForm((f) => ({ ...f, label: e.target.value }))}
                    placeholder="Investor Due Diligence"
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                </div>
                <div className="space-y-1 col-span-2">
                  <label className="text-xs font-medium text-gray-700">Folders</label>
                  <div className="space-y-1 max-h-40 overflow-y-auto border border-gray-200 rounded-md p-2">
                    {folders.map((f) => (
                      <label key={f.id} className="flex items-center gap-2 text-sm text-gray-700">
                        <input type="checkbox"
                          checked={shareForm.folder_ids.includes(f.id)}
                          onChange={(e) => setShareForm((sf) => ({
                            ...sf,
                            folder_ids: e.target.checked ? [...sf.folder_ids, f.id] : sf.folder_ids.filter((id) => id !== f.id),
                          }))} />
                        {f.name}
                      </label>
                    ))}
                  </div>
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-gray-700">Expires At (optional)</label>
                  <input type="date" value={shareForm.expires_at} onChange={(e) => setShareForm((f) => ({ ...f, expires_at: e.target.value }))}
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setShowShareForm(false)}>Cancel</Button>
                <Button disabled={actionLoading === "share_create"} onClick={createShare}
                  className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
                  {actionLoading === "share_create" ? "Creating…" : "Create Share Link"}
                </Button>
              </div>
            </div>
          )}
          <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
            {shares.length === 0 ? (
              <div className="py-12 text-center text-sm text-gray-500">No share links yet</div>
            ) : shares.map((s) => (
              <div key={s.id} className="px-5 py-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-900">{s.label}</p>
                    <p className="text-xs text-muted-foreground">
                      {s.view_count} views
                      {s.expires_at && ` · Expires ${new Date(s.expires_at).toLocaleDateString()}`}
                    </p>
                  </div>
                  <Button size="sm" variant="outline"
                    disabled={actionLoading === s.id + "_revoke"}
                    onClick={() => revokeShare(s.id)}
                    className="text-red-600 border-red-200 hover:bg-red-50">
                    Revoke
                  </Button>
                </div>
                <div className="flex items-center gap-2">
                  <input readOnly value={s.token}
                    className="flex-1 rounded-md border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-mono text-gray-600" />
                  <button type="button"
                    onClick={() => { navigator.clipboard.writeText(s.token); toast.success("Copied to clipboard"); }}
                    className="rounded-md border border-gray-200 p-1.5 hover:bg-gray-100">
                    <Copy className="h-3.5 w-3.5 text-gray-500" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
