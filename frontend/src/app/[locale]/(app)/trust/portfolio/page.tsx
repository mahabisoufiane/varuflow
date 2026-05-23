"use client";
import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const API = process.env.NEXT_PUBLIC_API_URL;
function getToken() {
  return typeof window !== "undefined" ? localStorage.getItem("auth_token") ?? "" : "";
}

interface Photo {
  id: string;
  staff_id: string;
  service_id: string | null;
  title: string;
  photo_url: string;
  description: string | null;
  is_featured: boolean;
}

export default function PortfolioPage() {
  const params = useParams();

  const [photos, setPhotos] = useState<Photo[]>([]);
  const [staffFilter, setStaffFilter] = useState("");
  const [featuredOnly, setFeaturedOnly] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [addOpen, setAddOpen] = useState(false);
  const [addForm, setAddForm] = useState({
    staff_id: "",
    service_id: "",
    title: "",
    photo_url: "",
    description: "",
    is_featured: false,
  });
  const [addError, setAddError] = useState("");
  const [addLoading, setAddLoading] = useState(false);

  const headers = {
    Authorization: `Bearer ${getToken()}`,
    "Content-Type": "application/json",
  };

  async function loadPhotos() {
    setLoading(true);
    setError("");
    try {
      const qs = new URLSearchParams({ featured_only: String(featuredOnly) });
      if (staffFilter) qs.set("staff_id", staffFilter);
      const res = await fetch(`${API}/api/portfolio?${qs}`, { headers });
      if (!res.ok) throw new Error("Failed to load portfolio");
      const data = await res.json();
      setPhotos(Array.isArray(data) ? data : data.items ?? []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load portfolio");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPhotos();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleAdd() {
    setAddLoading(true);
    setAddError("");
    try {
      const body: Record<string, unknown> = {
        staff_id: addForm.staff_id,
        title: addForm.title,
        photo_url: addForm.photo_url,
        is_featured: addForm.is_featured,
      };
      if (addForm.service_id) body.service_id = addForm.service_id;
      if (addForm.description) body.description = addForm.description;

      const res = await fetch(`${API}/api/portfolio`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("Failed to add photo");
      setAddOpen(false);
      setAddForm({
        staff_id: "", service_id: "", title: "", photo_url: "", description: "", is_featured: false,
      });
      loadPhotos();
    } catch (e: unknown) {
      setAddError(e instanceof Error ? e.message : "Failed to add photo");
    } finally {
      setAddLoading(false);
    }
  }

  async function handleFeature(id: string) {
    try {
      const res = await fetch(`${API}/api/portfolio/${id}/feature`, {
        method: "POST",
        headers,
      });
      if (!res.ok) throw new Error();
      loadPhotos();
    } catch {
      setError("Failed to feature photo");
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this photo?")) return;
    try {
      const res = await fetch(`${API}/api/portfolio/${id}`, { method: "DELETE", headers });
      if (!res.ok) throw new Error();
      loadPhotos();
    } catch {
      setError("Failed to delete photo");
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Staff Portfolio Gallery</h1>
        <Button onClick={() => setAddOpen(!addOpen)}>Add Photo</Button>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-4 flex flex-wrap gap-3 items-end">
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Staff ID</label>
            <Input
              value={staffFilter}
              onChange={(e) => setStaffFilter(e.target.value)}
              placeholder="UUID (optional)"
              className="w-56"
            />
          </div>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={featuredOnly}
              onChange={(e) => setFeaturedOnly(e.target.checked)}
            />
            Featured only
          </label>
          <Button variant="outline" onClick={loadPhotos}>Apply</Button>
        </CardContent>
      </Card>

      {/* Add form */}
      {addOpen && (
        <Card>
          <CardHeader><CardTitle>Add Photo</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <Input
              placeholder="Staff ID (UUID) *"
              value={addForm.staff_id}
              onChange={(e) => setAddForm((f) => ({ ...f, staff_id: e.target.value }))}
            />
            <Input
              placeholder="Service ID (optional)"
              value={addForm.service_id}
              onChange={(e) => setAddForm((f) => ({ ...f, service_id: e.target.value }))}
            />
            <Input
              placeholder="Title *"
              value={addForm.title}
              onChange={(e) => setAddForm((f) => ({ ...f, title: e.target.value }))}
            />
            <Input
              type="url"
              placeholder="Photo URL *"
              value={addForm.photo_url}
              onChange={(e) => setAddForm((f) => ({ ...f, photo_url: e.target.value }))}
            />
            <textarea
              className="w-full min-h-[60px] rounded-md border border-input bg-background px-3 py-2 text-sm"
              placeholder="Description"
              value={addForm.description}
              onChange={(e) => setAddForm((f) => ({ ...f, description: e.target.value }))}
            />
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={addForm.is_featured}
                onChange={(e) => setAddForm((f) => ({ ...f, is_featured: e.target.checked }))}
              />
              Featured
            </label>
            {addError && <p className="text-red-500 text-sm">{addError}</p>}
            <div className="flex gap-2">
              <Button onClick={handleAdd} disabled={addLoading}>
                {addLoading ? "Saving…" : "Save"}
              </Button>
              <Button variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {error && <p className="text-red-500 text-sm">{error}</p>}
      {loading && <p className="text-muted-foreground">Loading...</p>}

      {!loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {photos.length === 0 && (
            <p className="text-muted-foreground col-span-3 text-center py-8">No photos found</p>
          )}
          {photos.map((p) => (
            <Card key={p.id} className="overflow-hidden">
              <div className="aspect-video bg-muted relative overflow-hidden">
                {p.photo_url && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={p.photo_url}
                    alt={p.title}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = "none";
                    }}
                  />
                )}
                {p.is_featured && (
                  <div className="absolute top-2 right-2">
                    <Badge>Featured</Badge>
                  </div>
                )}
              </div>
              <CardContent className="pt-3 space-y-2">
                <h3 className="font-semibold text-sm">{p.title}</h3>
                {p.description && (
                  <p className="text-xs text-muted-foreground line-clamp-2">{p.description}</p>
                )}
                <div className="flex gap-2 pt-1">
                  {!p.is_featured && (
                    <Button size="sm" variant="outline" onClick={() => handleFeature(p.id)}>
                      Feature
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => handleDelete(p.id)}
                  >
                    Delete
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
