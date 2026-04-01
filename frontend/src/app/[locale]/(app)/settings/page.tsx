"use client";

import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { createClient } from "@/lib/supabase/client";
import { useEffect, useState } from "react";
import { Check } from "lucide-react";

interface Org {
  id: string; name: string; org_number: string | null;
  vat_number: string | null; address: string | null; plan: string;
}
interface Me { email: string; role: string; organization: Org; }

export default function SettingsPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  // Company form
  const [companyForm, setCompanyForm] = useState({ company_name: "", org_number: "", vat_number: "", address: "" });
  const [companySaving, setCompanySaving] = useState(false);
  const [companyOk, setCompanyOk] = useState(false);
  const [companyError, setCompanyError] = useState<string | null>(null);

  // Password form
  const [pwForm, setPwForm] = useState({ current: "", next: "", confirm: "" });
  const [pwSaving, setPwSaving] = useState(false);
  const [pwOk, setPwOk] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);

  useEffect(() => {
    api.get<Me>("/api/auth/me")
      .then((data) => {
        setMe(data);
        setCompanyForm({
          company_name: data.organization.name,
          org_number: data.organization.org_number ?? "",
          vat_number: data.organization.vat_number ?? "",
          address: data.organization.address ?? "",
        });
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  function setC(f: string, v: string) { setCompanyForm((s) => ({ ...s, [f]: v })); }
  function setP(f: string, v: string) { setPwForm((s) => ({ ...s, [f]: v })); }

  async function handleCompany(e: React.FormEvent) {
    e.preventDefault(); setCompanySaving(true); setCompanyError(null); setCompanyOk(false);
    try {
      await api.put("/api/auth/org", {
        company_name: companyForm.company_name,
        org_number: companyForm.org_number || null,
        vat_number: companyForm.vat_number || null,
        address: companyForm.address || null,
      });
      setCompanyOk(true);
      setTimeout(() => setCompanyOk(false), 3000);
    } catch (e: any) { setCompanyError(e.message); } finally { setCompanySaving(false); }
  }

  async function handlePassword(e: React.FormEvent) {
    e.preventDefault(); setPwError(null); setPwOk(false);
    if (pwForm.next !== pwForm.confirm) { setPwError("Passwords don't match"); return; }
    if (pwForm.next.length < 8) { setPwError("Minimum 8 characters"); return; }
    setPwSaving(true);
    try {
      const supabase = createClient();
      const { error } = await supabase.auth.updateUser({ password: pwForm.next });
      if (error) throw new Error(error.message);
      setPwForm({ current: "", next: "", confirm: "" });
      setPwOk(true);
      setTimeout(() => setPwOk(false), 3000);
    } catch (e: any) { setPwError(e.message); } finally { setPwSaving(false); }
  }

  if (loading) return (
    <div className="space-y-4 animate-pulse max-w-2xl">
      <div className="h-8 w-32 rounded bg-gray-100" />
      <div className="h-48 rounded-xl bg-gray-100" />
      <div className="h-48 rounded-xl bg-gray-100" />
    </div>
  );

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-[#1a2332]">Settings</h1>
        <p className="text-sm text-muted-foreground">Manage your account and organization</p>
      </div>

      {/* Account info (read-only) */}
      <div className="rounded-xl border bg-white p-6 space-y-4">
        <h2 className="font-semibold text-gray-900">Account</h2>
        <div className="space-y-1.5">
          <Label>Email</Label>
          <p className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-600">
            {me?.email}
          </p>
        </div>
        <div className="space-y-1.5">
          <Label>Role</Label>
          <p className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-600 capitalize">
            {me?.role.toLowerCase()}
          </p>
        </div>
        <div className="space-y-1.5">
          <Label>Plan</Label>
          <p className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-600 capitalize">
            {me?.organization.plan.toLowerCase()} {me?.organization.plan === "FREE" && "— Early access"}
          </p>
        </div>
      </div>

      {/* Company details */}
      <form onSubmit={handleCompany} className="rounded-xl border bg-white p-6 space-y-4">
        <h2 className="font-semibold text-gray-900">Company details</h2>
        <p className="text-xs text-muted-foreground">Shown on invoices and purchase orders.</p>
        {[
          { id: "company_name", label: "Company name *", placeholder: "Svensson AB", required: true },
          { id: "org_number", label: "Org number", placeholder: "556000-0000" },
          { id: "vat_number", label: "VAT number", placeholder: "SE556000000001" },
          { id: "address", label: "Address", placeholder: "Storgatan 1, Stockholm" },
        ].map(({ id, label, placeholder, required }) => (
          <div key={id} className="space-y-1.5">
            <Label htmlFor={id}>{label}</Label>
            <input id={id} required={required} value={(companyForm as any)[id]}
              onChange={(e) => setC(id, e.target.value)} placeholder={placeholder}
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
          </div>
        ))}
        {companyError && <p className="text-sm text-red-600">{companyError}</p>}
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={companySaving} className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
            {companySaving ? "Saving…" : "Save changes"}
          </Button>
          {companyOk && <span className="flex items-center gap-1 text-sm text-green-600"><Check className="h-4 w-4" />Saved</span>}
        </div>
      </form>

      {/* Change password */}
      <form onSubmit={handlePassword} className="rounded-xl border bg-white p-6 space-y-4">
        <h2 className="font-semibold text-gray-900">Change password</h2>
        {[
          { id: "next", label: "New password", placeholder: "Min. 8 characters", type: "password" },
          { id: "confirm", label: "Confirm new password", placeholder: "Repeat password", type: "password" },
        ].map(({ id, label, placeholder, type }) => (
          <div key={id} className="space-y-1.5">
            <Label htmlFor={id}>{label}</Label>
            <input id={id} type={type} required minLength={8} value={(pwForm as any)[id]}
              onChange={(e) => setP(id, e.target.value)} placeholder={placeholder}
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
          </div>
        ))}
        {pwError && <p className="text-sm text-red-600">{pwError}</p>}
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={pwSaving} className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
            {pwSaving ? "Updating…" : "Update password"}
          </Button>
          {pwOk && <span className="flex items-center gap-1 text-sm text-green-600"><Check className="h-4 w-4" />Updated</span>}
        </div>
      </form>
    </div>
  );
}
