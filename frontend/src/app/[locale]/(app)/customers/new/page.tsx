"use client";

import { api } from "@/lib/api-client";
import { useRouter, useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";
import { Label } from "@/components/ui/label";

const FIELDS = [
  { id: "company_name",       label: "Company name",         span: true,  required: true,  placeholder: "Nordisk Handel AB",     type: "text"   },
  { id: "org_number",         label: "Org number",           span: false, required: false, placeholder: "556123-4567",            type: "text"   },
  { id: "vat_number",         label: "VAT number",           span: false, required: false, placeholder: "SE556123456701",         type: "text"   },
  { id: "email",              label: "Email",                span: false, required: false, placeholder: "orders@company.se",      type: "email"  },
  { id: "phone",              label: "Phone",                span: false, required: false, placeholder: "+46 8 123 456",          type: "tel"    },
  { id: "address",            label: "Address",              span: true,  required: false, placeholder: "Storgatan 1, Stockholm", type: "text"   },
  { id: "payment_terms_days", label: "Payment terms (days)", span: false, required: false, placeholder: "30",                    type: "number" },
];

const EMPTY: Record<string, string> = {
  company_name: "", org_number: "", vat_number: "",
  email: "", phone: "", address: "", payment_terms_days: "30",
};

export default function NewCustomerPage() {
  const router = useRouter();
  const params = useParams();
  const locale = params.locale as string;

  const [form, setForm]   = useState({ ...EMPTY });
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState<string | null>(null);

  function set(field: string, value: string) {
    setForm(s => ({ ...s, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.post("/api/invoicing/customers", {
        company_name: form.company_name,
        org_number: form.org_number || null,
        vat_number: form.vat_number || null,
        email: form.email || null,
        phone: form.phone || null,
        address: form.address || null,
        payment_terms_days: Number(form.payment_terms_days) || 30,
      });
      toast.success("Customer created");
      router.push(`/${locale}/customers`);
    } catch (e: unknown) {
      setError((e as Error).message ?? "Something went wrong");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          href={`/${locale}/customers`}
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.08] text-slate-500 hover:bg-white/5 hover:text-slate-300 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <h1 className="text-xl font-bold text-slate-100">New customer</h1>
          <p className="text-xs text-slate-600 mt-0.5">Add a new B2B customer to your account</p>
        </div>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="rounded-xl border border-white/[0.06] bg-vf-surface p-6 space-y-5">
        <div className="grid grid-cols-2 gap-4">
          {FIELDS.map(({ id, label, span, required, placeholder, type }) => (
            <div key={id} className={`space-y-1.5 ${span ? "col-span-2" : ""}`}>
              <Label htmlFor={id} className="text-xs font-medium text-slate-400">
                {label}{required && <span className="text-red-400 ml-0.5">*</span>}
              </Label>
              <input
                id={id}
                type={type}
                required={required}
                min={id === "payment_terms_days" ? "0" : undefined}
                max={id === "payment_terms_days" ? "365" : undefined}
                value={form[id]}
                onChange={e => set(id, e.target.value)}
                placeholder={placeholder}
                className="vf-input"
              />
            </div>
          ))}
        </div>

        {error && (
          <div className="flex items-start gap-2 rounded-lg bg-red-500/10 border border-red-500/20 px-3.5 py-2.5 text-sm text-red-400">
            <span className="mt-0.5 shrink-0">⚠</span>
            {error}
          </div>
        )}

        <div className="flex items-center justify-end gap-3 pt-1">
          <Link
            href={`/${locale}/customers`}
            className="vf-btn-ghost text-sm"
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={saving}
            className="vf-btn disabled:opacity-50"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {saving ? "Creating…" : "Create customer"}
          </button>
        </div>
      </form>
    </div>
  );
}
