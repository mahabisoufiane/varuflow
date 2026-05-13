"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { PlusCircle, Trash2, Users2, RefreshCw, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface CrossEntityRole {
  id: string;
  user_id: string;
  org_id: string;
  role: string;
  granted_by_user_id: string | null;
  created_at: string;
}

interface Entity {
  id: string;
  name: string;
}

const ROLE_COLORS: Record<string, string> = {
  owner:  "bg-red-100 text-red-700",
  admin:  "bg-orange-100 text-orange-700",
  member: "bg-blue-100 text-blue-700",
  viewer: "bg-gray-100 text-gray-600",
};

export default function MultiEntityPermissionsPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [roles, setRoles] = useState<CrossEntityRole[]>([]);
  const [entities, setEntities] = useState<Entity[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ user_id: "", org_id: "", role: "viewer" });
  const [saving, setSaving] = useState(false);

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

      const [rolesRes, entitiesRes] = await Promise.all([
        fetch(apiUrl("/api/multi-entity/permissions"), { headers: { Authorization: `Bearer ${token}` } }),
        fetch(apiUrl("/api/multi-entity/entities"), { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (rolesRes.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (rolesRes.ok) setRoles(await rolesRes.json());
      if (entitiesRes.ok) {
        const data = await entitiesRes.json();
        setEntities(Array.isArray(data) ? data : data.entities ?? []);
      }
    } catch {
      toast.error("Failed to load permissions");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function assignRole() {
    if (!form.user_id.trim() || !form.org_id) { toast.error("User ID and entity are required"); return; }
    setSaving(true);
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/multi-entity/permissions"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to assign role");
        return;
      }
      toast.success("Role assigned");
      setShowForm(false);
      setForm({ user_id: "", org_id: "", role: "viewer" });
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setSaving(false);
    }
  }

  async function removeRole(id: string) {
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/multi-entity/permissions/${id}`), {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { toast.error("Failed to remove"); return; }
      toast.success("Permission removed");
      await load();
    } catch {
      toast.error("Something went wrong");
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
            <Shield className="h-5 w-5" /> Cross-Entity Permissions
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Assign users different roles in different subsidiaries within the group.
            For example, a user can be Admin in HQ but Viewer in a branch.
          </p>
        </div>
        <Button onClick={() => setShowForm(true)} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> Assign Role
        </Button>
      </div>

      <div className="rounded-xl border bg-amber-50 border-amber-200 px-5 py-3">
        <p className="text-sm text-amber-800">
          <strong>Note:</strong> These role overrides apply to subsidiary entities only.
          A user&apos;s base role in their primary org is set via Settings → Team.
        </p>
      </div>

      {/* Assign form */}
      {showForm && (
        <div className="rounded-xl border border-[#1a2332]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Assign Cross-Entity Role</h3>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">User ID (UUID)</label>
            <input
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              value={form.user_id}
              onChange={(e) => setForm((f) => ({ ...f, user_id: e.target.value }))}
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
            />
            <p className="text-xs text-muted-foreground">Find the user ID from Settings → Team → member row.</p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Entity (subsidiary)</label>
              <select
                value={form.org_id}
                onChange={(e) => setForm((f) => ({ ...f, org_id: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
              >
                <option value="">Select entity…</option>
                {entities.map((e) => (
                  <option key={e.id} value={e.id}>{e.name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Role</label>
              <select
                value={form.role}
                onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
              >
                <option value="owner">Owner</option>
                <option value="admin">Admin</option>
                <option value="member">Member</option>
                <option value="viewer">Viewer</option>
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
            <Button disabled={saving} onClick={assignRole} className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
              {saving ? "Saving…" : "Assign Role"}
            </Button>
          </div>
        </div>
      )}

      {/* Roles list */}
      <div className="rounded-xl border bg-white shadow-sm">
        {loading && roles.length === 0 ? (
          <div className="px-5 py-8 text-center">
            <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
          </div>
        ) : roles.length === 0 ? (
          <div className="px-5 py-12 text-center">
            <Users2 className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <p className="text-gray-600 font-medium">No cross-entity roles assigned</p>
            <p className="text-sm text-muted-foreground mt-1">
              All group users currently use their default organization role.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            <div className="grid grid-cols-4 gap-4 px-5 py-2.5 bg-gray-50 text-xs font-medium text-muted-foreground uppercase tracking-wide">
              <span className="col-span-2">User ID</span>
              <span>Entity</span>
              <span>Role</span>
            </div>
            {roles.map((r) => {
              const entity = entities.find((e) => e.id === r.org_id);
              return (
                <div key={r.id} className="grid grid-cols-4 gap-4 items-center px-5 py-3">
                  <span className="col-span-2 font-mono text-xs text-gray-600 truncate">{r.user_id}</span>
                  <span className="text-sm text-gray-700 truncate">{entity?.name ?? r.org_id.slice(0, 8) + "…"}</span>
                  <div className="flex items-center justify-between">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${ROLE_COLORS[r.role] ?? "bg-gray-100 text-gray-600"}`}>
                      {r.role}
                    </span>
                    <button type="button" onClick={() => removeRole(r.id)}
                      className="text-muted-foreground hover:text-red-600 transition-colors">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
