"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { portalApi, PORTAL_TOKEN_KEY } from "@/lib/portal-client";

interface Profile { id: string; company_name: string; email: string | null; phone: string | null; address: string | null; org_number: string | null; }

export default function PortalProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [form, setForm] = useState({ email: "", phone: "", address: "" });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(PORTAL_TOKEN_KEY)) { router.replace("/portal/login"); return; }
    portalApi.get<Profile>("/api/portal/profile").then(p => {
      setProfile(p);
      setForm({ email: p.email || "", phone: p.phone || "", address: p.address || "" });
    });
  }, []);

  const save = async () => {
    setSaving(true);
    await portalApi.post("/api/portal/profile", form);
    setSaving(false);
  };

  if (!profile) return <div className="p-4">Loading...</div>;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">My Profile</h1>
      <div className="bg-white border rounded p-4 space-y-3">
        <div><label className="text-sm text-gray-500">Company</label><p className="font-medium">{profile.company_name}</p></div>
        <div><label className="text-sm text-gray-500">Org Number</label><p>{profile.org_number || "—"}</p></div>
        <div><label className="text-sm text-gray-500">Email</label><input value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} className="w-full border rounded px-3 py-2" /></div>
        <div><label className="text-sm text-gray-500">Phone</label><input value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} className="w-full border rounded px-3 py-2" /></div>
        <div><label className="text-sm text-gray-500">Address</label><input value={form.address} onChange={e => setForm({ ...form, address: e.target.value })} className="w-full border rounded px-3 py-2" /></div>
        <button onClick={save} disabled={saving} className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">{saving ? "Saving..." : "Save Changes"}</button>
      </div>
    </div>
  );
}
