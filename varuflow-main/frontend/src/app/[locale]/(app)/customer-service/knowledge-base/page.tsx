"use client";
import { useState, useEffect, useRef } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const API = process.env.NEXT_PUBLIC_API_URL;
function getToken() {
  return typeof window !== "undefined" ? localStorage.getItem("auth_token") ?? "" : "";
}

interface KbCategory {
  id: string;
  name: string;
  sort_order: number;
}

interface KbArticle {
  id: string;
  title: string;
  category_id: string | null;
  body: string;
  is_published: boolean;
  views: number;
  helpful: number;
  not_helpful: number;
}

export default function KnowledgeBasePage() {
  const params = useParams();

  const [categories, setCategories] = useState<KbCategory[]>([]);
  const [articles, setArticles] = useState<KbArticle[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Category form
  const [catName, setCatName] = useState("");
  const [catOrder, setCatOrder] = useState("");
  const [catError, setCatError] = useState("");
  const [catSaving, setCatSaving] = useState(false);

  // Article form
  const [artOpen, setArtOpen] = useState(false);
  const [artForm, setArtForm] = useState({
    title: "",
    category_id: "",
    body: "",
    is_published: false,
  });
  const [artError, setArtError] = useState("");
  const [artSaving, setArtSaving] = useState(false);

  // Edit article
  const [editId, setEditId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ title: "", body: "", is_published: false });
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState("");

  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const headers = {
    Authorization: `Bearer ${getToken()}`,
    "Content-Type": "application/json",
  };

  async function loadCategories() {
    try {
      const res = await fetch(`${API}/api/kb/categories`, { headers });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setCategories(Array.isArray(data) ? data : data.items ?? []);
    } catch {
      // non-blocking
    }
  }

  async function loadArticles(search: string) {
    setLoading(true);
    setError("");
    try {
      const qs = search ? `?search=${encodeURIComponent(search)}` : "";
      const res = await fetch(`${API}/api/kb/articles${qs}`, { headers });
      if (!res.ok) throw new Error("Failed to load articles");
      const data = await res.json();
      setArticles(Array.isArray(data) ? data : data.items ?? []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load articles");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCategories();
    loadArticles("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSearchChange(val: string) {
    setSearchTerm(val);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => loadArticles(val), 300);
  }

  async function handleAddCategory() {
    setCatSaving(true);
    setCatError("");
    try {
      const res = await fetch(`${API}/api/kb/categories`, {
        method: "POST",
        headers,
        body: JSON.stringify({ name: catName, sort_order: catOrder ? Number(catOrder) : 0 }),
      });
      if (!res.ok) throw new Error("Failed to add category");
      setCatName("");
      setCatOrder("");
      loadCategories();
    } catch (e: unknown) {
      setCatError(e instanceof Error ? e.message : "Failed to add category");
    } finally {
      setCatSaving(false);
    }
  }

  async function handleDeleteCategory(id: string) {
    if (!confirm("Delete this category?")) return;
    try {
      const res = await fetch(`${API}/api/kb/categories/${id}`, { method: "DELETE", headers });
      if (!res.ok) throw new Error();
      loadCategories();
    } catch {
      setError("Failed to delete category");
    }
  }

  async function handleAddArticle() {
    setArtSaving(true);
    setArtError("");
    try {
      const body: Record<string, unknown> = {
        title: artForm.title,
        body: artForm.body,
        is_published: artForm.is_published,
      };
      if (artForm.category_id) body.category_id = artForm.category_id;

      const res = await fetch(`${API}/api/kb/articles`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("Failed to create article");
      setArtOpen(false);
      setArtForm({ title: "", category_id: "", body: "", is_published: false });
      loadArticles(searchTerm);
    } catch (e: unknown) {
      setArtError(e instanceof Error ? e.message : "Failed to create article");
    } finally {
      setArtSaving(false);
    }
  }

  async function handleEditSave(id: string) {
    setEditSaving(true);
    setEditError("");
    try {
      const res = await fetch(`${API}/api/kb/articles/${id}`, {
        method: "PATCH",
        headers,
        body: JSON.stringify(editForm),
      });
      if (!res.ok) throw new Error("Failed to update article");
      setEditId(null);
      loadArticles(searchTerm);
    } catch (e: unknown) {
      setEditError(e instanceof Error ? e.message : "Failed to update article");
    } finally {
      setEditSaving(false);
    }
  }

  async function handleDeleteArticle(id: string) {
    if (!confirm("Delete this article?")) return;
    try {
      const res = await fetch(`${API}/api/kb/articles/${id}`, { method: "DELETE", headers });
      if (!res.ok) throw new Error();
      loadArticles(searchTerm);
    } catch {
      setError("Failed to delete article");
    }
  }

  function catName_(id: string | null) {
    if (!id) return "—";
    return categories.find((c) => c.id === id)?.name ?? id.slice(0, 8) + "…";
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Knowledge Base</h1>

      {/* Categories */}
      <Card>
        <CardHeader><CardTitle>Categories</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {categories.map((c) => (
              <div key={c.id} className="flex items-center gap-1 border rounded-md px-2 py-1 text-sm">
                <span>{c.name}</span>
                <span className="text-xs text-muted-foreground">(order: {c.sort_order})</span>
                <button
                  className="ml-1 text-red-500 hover:text-red-700 text-xs font-bold"
                  onClick={() => handleDeleteCategory(c.id)}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
          <div className="flex gap-2 items-end">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Name *</label>
              <Input
                value={catName}
                onChange={(e) => setCatName(e.target.value)}
                placeholder="Category name"
                className="w-48"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Sort Order</label>
              <Input
                type="number"
                value={catOrder}
                onChange={(e) => setCatOrder(e.target.value)}
                placeholder="0"
                className="w-20"
              />
            </div>
            <Button onClick={handleAddCategory} disabled={catSaving || !catName.trim()}>
              {catSaving ? "Adding…" : "Add Category"}
            </Button>
          </div>
          {catError && <p className="text-red-500 text-sm">{catError}</p>}
        </CardContent>
      </Card>

      {/* Articles */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Articles</CardTitle>
            <Button onClick={() => setArtOpen(!artOpen)}>New Article</Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input
            value={searchTerm}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Search articles…"
            className="w-full sm:w-72"
          />

          {/* New article form */}
          {artOpen && (
            <div className="border rounded-lg p-4 space-y-3 bg-muted/30">
              <h3 className="font-semibold text-sm">New Article</h3>
              <Input
                placeholder="Title *"
                value={artForm.title}
                onChange={(e) => setArtForm((f) => ({ ...f, title: e.target.value }))}
              />
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Category</label>
                <select
                  value={artForm.category_id}
                  onChange={(e) => setArtForm((f) => ({ ...f, category_id: e.target.value }))}
                  className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm w-full"
                >
                  <option value="">No category</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Body (Markdown)</label>
                <textarea
                  className="w-full min-h-[120px] rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
                  value={artForm.body}
                  onChange={(e) => setArtForm((f) => ({ ...f, body: e.target.value }))}
                  placeholder="Write article content in Markdown…"
                />
              </div>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={artForm.is_published}
                  onChange={(e) => setArtForm((f) => ({ ...f, is_published: e.target.checked }))}
                />
                Published
              </label>
              {artError && <p className="text-red-500 text-sm">{artError}</p>}
              <div className="flex gap-2">
                <Button onClick={handleAddArticle} disabled={artSaving}>
                  {artSaving ? "Saving…" : "Create"}
                </Button>
                <Button variant="outline" onClick={() => setArtOpen(false)}>Cancel</Button>
              </div>
            </div>
          )}

          {error && <p className="text-red-500 text-sm">{error}</p>}
          {loading && <p className="text-muted-foreground">Loading...</p>}

          {!loading && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Published</TableHead>
                  <TableHead>Views</TableHead>
                  <TableHead>Helpful / Not</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {articles.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                      No articles found
                    </TableCell>
                  </TableRow>
                )}
                {articles.map((a) => (
                  <>
                    <TableRow key={a.id}>
                      <TableCell className="font-medium">{a.title}</TableCell>
                      <TableCell>{catName_(a.category_id)}</TableCell>
                      <TableCell>
                        <Badge variant={a.is_published ? "default" : "secondary"}>
                          {a.is_published ? "Published" : "Draft"}
                        </Badge>
                      </TableCell>
                      <TableCell>{a.views ?? 0}</TableCell>
                      <TableCell>
                        {a.helpful ?? 0} / {a.not_helpful ?? 0}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              if (editId === a.id) {
                                setEditId(null);
                              } else {
                                setEditId(a.id);
                                setEditForm({
                                  title: a.title,
                                  body: a.body,
                                  is_published: a.is_published,
                                });
                              }
                            }}
                          >
                            {editId === a.id ? "Cancel" : "Edit"}
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => handleDeleteArticle(a.id)}
                          >
                            Delete
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                    {editId === a.id && (
                      <TableRow key={`edit-${a.id}`}>
                        <TableCell colSpan={6} className="bg-muted/30">
                          <div className="p-3 space-y-3">
                            <Input
                              value={editForm.title}
                              onChange={(e) =>
                                setEditForm((f) => ({ ...f, title: e.target.value }))
                              }
                              placeholder="Title"
                            />
                            <textarea
                              className="w-full min-h-[100px] rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
                              value={editForm.body}
                              onChange={(e) =>
                                setEditForm((f) => ({ ...f, body: e.target.value }))
                              }
                            />
                            <label className="flex items-center gap-2 text-sm cursor-pointer">
                              <input
                                type="checkbox"
                                checked={editForm.is_published}
                                onChange={(e) =>
                                  setEditForm((f) => ({ ...f, is_published: e.target.checked }))
                                }
                              />
                              Published
                            </label>
                            {editError && <p className="text-red-500 text-sm">{editError}</p>}
                            <Button
                              size="sm"
                              onClick={() => handleEditSave(a.id)}
                              disabled={editSaving}
                            >
                              {editSaving ? "Saving…" : "Save"}
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
