"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

interface Persona {
  id: string;
  name: string;
  description: string;
  segment_size: number;
  behavior_traits: string[];
  last_computed_at: string;
}

export default function PersonasPage() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [loading, setLoading] = useState(false);
  const [computing, setComputing] = useState(false);
  const [error, setError] = useState("");

  // Inline edit state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [saving, setSaving] = useState(false);

  async function fetchPersonas() {
    setLoading(true);
    setError("");
    try {
      setPersonas(await api.get<Persona[]>("/api/ai/personas"));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load personas");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchPersonas();
  }, []);

  async function computePersonas() {
    setComputing(true);
    setError("");
    try {
      await api.post("/api/ai/personas/compute", {});
      await fetchPersonas();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Compute failed");
    } finally {
      setComputing(false);
    }
  }

  function startEdit(persona: Persona) {
    setEditingId(persona.id);
    setEditName(persona.name);
    setEditDescription(persona.description);
  }

  async function saveEdit(id: string) {
    setSaving(true);
    try {
      await api.patch(`/api/ai/personas/${id}`, { name: editName, description: editDescription });
      setEditingId(null);
      await fetchPersonas();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function deletePersona(id: string) {
    try {
      await api.delete(`/api/ai/personas/${id}`);
      await fetchPersonas();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">AI Customer Personas</h1>
        <Button onClick={computePersonas} disabled={computing}>
          {computing ? (
            <span className="flex items-center gap-2">
              <span className="h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Computing…
            </span>
          ) : (
            "Compute Personas"
          )}
        </Button>
      </div>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      {loading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : personas.length === 0 ? (
        <Card>
          <CardContent className="pt-6">
            <p className="text-muted-foreground text-center">
              No personas computed yet. Click "Compute Personas" to generate them.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {personas.map((persona) => (
            <Card key={persona.id} className="relative">
              <CardHeader className="pb-2">
                {editingId === persona.id ? (
                  <Input
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="font-bold text-base"
                    autoFocus
                  />
                ) : (
                  <CardTitle
                    className="text-base cursor-pointer hover:underline"
                    onClick={() => startEdit(persona)}
                    title="Click to edit"
                  >
                    {persona.name}
                  </CardTitle>
                )}
                <Badge variant="secondary" className="w-fit mt-1">
                  {persona.segment_size} customers
                </Badge>
              </CardHeader>
              <CardContent className="space-y-3">
                {editingId === persona.id ? (
                  <>
                    <textarea
                      className="w-full border rounded px-3 py-2 text-sm bg-background min-h-[80px] resize-y"
                      value={editDescription}
                      onChange={(e) => setEditDescription(e.target.value)}
                    />
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => saveEdit(persona.id)} disabled={saving}>
                        {saving ? "Saving…" : "Save"}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setEditingId(null)}
                      >
                        Cancel
                      </Button>
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">{persona.description}</p>
                )}

                {persona.behavior_traits && persona.behavior_traits.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {persona.behavior_traits.map((trait, i) => (
                      <Badge key={i} variant="outline" className="text-xs">
                        {trait}
                      </Badge>
                    ))}
                  </div>
                )}

                <div className="flex items-center justify-between pt-1">
                  <span className="text-xs text-muted-foreground">
                    Last computed: {new Date(persona.last_computed_at).toLocaleDateString()}
                  </span>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => deletePersona(persona.id)}
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
