"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { RefreshCw, Users, Trash2, ChevronDown, ChevronRight, PlusCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface FamilyMember {
  id: string;
  name: string;
  relationship: string;
  date_of_birth: string | null;
  customer_id: string | null;
}

interface FamilyGroup {
  id: string;
  primary_customer_id: string;
  name: string;
  shared_loyalty: boolean;
  members: FamilyMember[];
}

const RELATIONSHIP_OPTIONS = ["partner", "child", "parent", "sibling", "other"];

const RELATIONSHIP_BADGE: Record<string, string> = {
  partner: "bg-pink-100 text-pink-700",
  child: "bg-yellow-100 text-yellow-700",
  parent: "bg-blue-100 text-blue-700",
  sibling: "bg-purple-100 text-purple-700",
  other: "bg-gray-100 text-gray-700",
};

export default function FamilyAccountsPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [groups, setGroups] = useState<FamilyGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedGroup, setExpandedGroup] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createForm, setCreateForm] = useState({
    primary_customer_id: "",
    name: "",
    shared_loyalty: true,
  });

  const [addMemberForms, setAddMemberForms] = useState<Record<string, {
    name: string; relationship: string; date_of_birth: string; customer_id: string;
  }>>({});

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
      const res = await fetch(apiUrl("/api/family"), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (res.ok) setGroups(await res.json());
    } catch {
      toast.error("Failed to load family accounts");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function createGroup() {
    if (!createForm.primary_customer_id.trim()) { toast.error("Primary customer ID is required"); return; }
    setActionLoading("create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/family"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(createForm),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to create group");
        return;
      }
      toast.success("Family group created");
      setShowCreateForm(false);
      setCreateForm({ primary_customer_id: "", name: "", shared_loyalty: true });
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function deleteGroup(id: string) {
    setActionLoading(id + "_delete");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/family/${id}`), {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to delete group");
        return;
      }
      toast.success("Family group deleted");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function addMember(groupId: string) {
    const form = addMemberForms[groupId];
    if (!form || !form.name.trim()) { toast.error("Member name is required"); return; }
    setActionLoading(groupId + "_add_member");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/family/${groupId}/members`), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          name: form.name,
          relationship: form.relationship,
          date_of_birth: form.date_of_birth || null,
          customer_id: form.customer_id || null,
        }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to add member");
        return;
      }
      toast.success("Member added");
      setAddMemberForms((f) => ({ ...f, [groupId]: { name: "", relationship: "partner", date_of_birth: "", customer_id: "" } }));
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function removeMember(groupId: string, memberId: string) {
    setActionLoading(memberId + "_remove");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/family/${groupId}/members/${memberId}`), {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to remove member");
        return;
      }
      toast.success("Member removed");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  function initAddMemberForm(groupId: string) {
    if (!addMemberForms[groupId]) {
      setAddMemberForms((f) => ({ ...f, [groupId]: { name: "", relationship: "partner", date_of_birth: "", customer_id: "" } }));
    }
  }

  const inputCls = "block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]";

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Family Accounts</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Manage family groups with shared loyalty benefits.</p>
        </div>
        <Button onClick={() => setShowCreateForm((s) => !s)} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> New Family Group
        </Button>
      </div>

      {/* Create form */}
      {showCreateForm && (
        <div className="rounded-xl border border-[#1a2332]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Create Family Group</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Primary Customer ID *</label>
              <input value={createForm.primary_customer_id}
                onChange={(e) => setCreateForm((f) => ({ ...f, primary_customer_id: e.target.value }))}
                placeholder="UUID" className={inputCls} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Group Name</label>
              <input value={createForm.name}
                onChange={(e) => setCreateForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="The Andersons" className={inputCls} />
            </div>
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={createForm.shared_loyalty}
              onChange={(e) => setCreateForm((f) => ({ ...f, shared_loyalty: e.target.checked }))}
              className="h-4 w-4 rounded border-gray-300" />
            <span className="text-sm text-gray-700">Shared loyalty (points pooled across all members)</span>
          </label>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowCreateForm(false)}>Cancel</Button>
            <Button disabled={actionLoading === "create"} onClick={createGroup}
              className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
              {actionLoading === "create" ? "Creating…" : "Create Group"}
            </Button>
          </div>
        </div>
      )}

      {/* Group list */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : groups.length === 0 ? (
        <div className="rounded-xl border bg-white shadow-sm py-12 text-center">
          <Users className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-gray-600 font-medium">No family groups yet</p>
        </div>
      ) : (
        <div className="space-y-3">
          {groups.map((g) => {
            const isExpanded = expandedGroup === g.id;
            const memberForm = addMemberForms[g.id];
            return (
              <div key={g.id} className="rounded-xl border bg-white shadow-sm">
                {/* Group header */}
                <div className="flex items-center gap-3 px-5 py-4">
                  <button type="button"
                    onClick={() => {
                      setExpandedGroup(isExpanded ? null : g.id);
                      initAddMemberForm(g.id);
                    }}
                    className="flex items-center gap-2 flex-1 min-w-0 text-left">
                    {isExpanded
                      ? <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      : <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />}
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900">{g.name || "Unnamed Group"}</p>
                      <p className="text-xs text-muted-foreground font-mono">{g.primary_customer_id.slice(0, 8)}…</p>
                    </div>
                  </button>
                  <span className="text-xs text-muted-foreground">{g.members.length} members</span>
                  {g.shared_loyalty && (
                    <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium bg-green-100 text-green-700">
                      Shared Loyalty
                    </span>
                  )}
                  <Button variant="ghost" size="sm" disabled={actionLoading === g.id + "_delete"}
                    onClick={() => deleteGroup(g.id)}>
                    {actionLoading === g.id + "_delete"
                      ? <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                      : <Trash2 className="h-3.5 w-3.5 text-red-500" />}
                  </Button>
                </div>

                {/* Expanded members */}
                {isExpanded && (
                  <div className="border-t border-gray-100 px-5 py-4 space-y-4">
                    {g.members.length === 0 ? (
                      <p className="text-xs text-muted-foreground text-center py-2">No members yet</p>
                    ) : (
                      <div className="divide-y divide-gray-100">
                        {g.members.map((m) => (
                          <div key={m.id} className="flex items-center gap-3 py-2.5">
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-gray-900">{m.name}</p>
                              <div className="flex items-center gap-2 mt-0.5">
                                {m.date_of_birth && (
                                  <span className="text-xs text-muted-foreground">
                                    {new Date(m.date_of_birth).toLocaleDateString()}
                                  </span>
                                )}
                                {m.customer_id && (
                                  <span className="text-xs font-mono text-muted-foreground">{m.customer_id.slice(0, 8)}…</span>
                                )}
                              </div>
                            </div>
                            <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${RELATIONSHIP_BADGE[m.relationship] ?? "bg-gray-100 text-gray-700"}`}>
                              {m.relationship}
                            </span>
                            <Button variant="ghost" size="sm" disabled={actionLoading === m.id + "_remove"}
                              onClick={() => removeMember(g.id, m.id)}>
                              {actionLoading === m.id + "_remove"
                                ? <RefreshCw className="h-3 w-3 animate-spin" />
                                : <Trash2 className="h-3.5 w-3.5 text-red-500" />}
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Add member form */}
                    {memberForm && (
                      <div className="pt-2 border-t border-gray-100 space-y-3">
                        <p className="text-xs font-semibold text-gray-700">Add Member</p>
                        <div className="grid grid-cols-2 gap-3">
                          <div className="space-y-1">
                            <label className="text-xs font-medium text-gray-700">Name *</label>
                            <input value={memberForm.name}
                              onChange={(e) => setAddMemberForms((f) => ({ ...f, [g.id]: { ...f[g.id], name: e.target.value } }))}
                              placeholder="Full name" className={inputCls} />
                          </div>
                          <div className="space-y-1">
                            <label className="text-xs font-medium text-gray-700">Relationship</label>
                            <select value={memberForm.relationship}
                              onChange={(e) => setAddMemberForms((f) => ({ ...f, [g.id]: { ...f[g.id], relationship: e.target.value } }))}
                              className={inputCls}>
                              {RELATIONSHIP_OPTIONS.map((r) => (
                                <option key={r} value={r} className="capitalize">{r}</option>
                              ))}
                            </select>
                          </div>
                          <div className="space-y-1">
                            <label className="text-xs font-medium text-gray-700">Date of Birth</label>
                            <input type="date" value={memberForm.date_of_birth}
                              onChange={(e) => setAddMemberForms((f) => ({ ...f, [g.id]: { ...f[g.id], date_of_birth: e.target.value } }))}
                              className={inputCls} />
                          </div>
                          <div className="space-y-1">
                            <label className="text-xs font-medium text-gray-700">Linked Customer ID (optional)</label>
                            <input value={memberForm.customer_id}
                              onChange={(e) => setAddMemberForms((f) => ({ ...f, [g.id]: { ...f[g.id], customer_id: e.target.value } }))}
                              placeholder="UUID" className={inputCls} />
                          </div>
                        </div>
                        <Button size="sm" disabled={actionLoading === g.id + "_add_member"} onClick={() => addMember(g.id)}
                          className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
                          {actionLoading === g.id + "_add_member" ? "Adding…" : "Add Member"}
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
