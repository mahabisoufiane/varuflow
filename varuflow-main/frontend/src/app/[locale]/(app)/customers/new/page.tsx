"use client";

import { api } from "@/lib/api-client";
import { useRouter } from "@/i18n/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { ArrowLeft, Building2, Hash, Globe, Mail, Phone, MessageCircle, MapPin, Clock, Loader2, AlertCircle } from "lucide-react";
import { Link } from "@/i18n/navigation";

const FIELDS = [
  { id: "company_name",       label: "Company name",         icon: Building2, span: true,  required: true,  placeholder: "Nordisk Handel AB",     type: "text"   },
  { id: "org_number",         label: "Org number",           icon: Hash,      span: false, required: false, placeholder: "556123-4567",            type: "text"   },
  { id: "vat_number",         label: "VAT number",           icon: Globe,     span: false, required: false, placeholder: "SE556123456701",         type: "text"   },
  { id: "email",              label: "Email",                icon: Mail,      span: false, required: false, placeholder: "orders@company.se",      type: "email"  },
  { id: "phone",              label: "Phone",                icon: Phone,     span: false, required: false, placeholder: "+46 8 123 456",          type: "tel"    },
  { id: "whatsapp_number",    label: "WhatsApp",             icon: MessageCircle, span: false, required: false, placeholder: "+46 70 123 45 67",  type: "tel"    },
  { id: "address",            label: "Address",              icon: MapPin,    span: true,  required: false, placeholder: "Storgatan 1, Stockholm", type: "text"   },
  { id: "payment_terms_days", label: "Payment terms (days)", icon: Clock,     span: false, required: false, placeholder: "30",                    type: "number" },
] as const;

const EMPTY: Record<string, string> = {
  company_name: "", org_number: "", vat_number: "",
  email: "", phone: "", whatsapp_number: "",
  address: "", payment_terms_days: "30",
};

export default function NewCustomerPage() {
  const router = useRouter();

  const [form, setForm]     = useState({ ...EMPTY });
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
        company_name:       form.company_name,
        org_number:         form.org_number || null,
        vat_number:         form.vat_number || null,
        email:              form.email || null,
        phone:              form.phone || null,
        whatsapp_number:    form.whatsapp_number || null,
        address:            form.address || null,
        payment_terms_days: Number(form.payment_terms_days) || 30,
      });
      toast.success("Customer created");
      router.push("/customers");
    } catch (e: unknown) {
      setError((e as Error).message ?? "Something went wrong");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">

      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="flex items-center gap-4">
        <Link
          href="/customers"
          className="flex h-9 w-9 items-center justify-center rounded-xl transition-colors vf-btn-ghost"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <h1 className="text-xl font-bold vf-text-1">New customer</h1>
          <p className="text-xs vf-text-m mt-0.5">Add a new B2B customer to your account</p>
        </div>
      </div>

      {/* ── Form card ───────────────────────────────────────────────── */}
      <form onSubmit={handleSubmit} className="vf-section p-6 space-y-5 rounded-2xl">

        {/* Section label */}
        <div className="pb-1 border-b border-[var(--vf-divider)]">
          <p className="text-[11px] font-semibold uppercase tracking-widest vf-text-m">Company details</p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          {FIELDS.map(({ id, label, icon: Icon, span, required, placeholder, type }) => (
            <div key={id} className={`space-y-1.5 ${span ? "col-span-2" : ""}`}>
              <label htmlFor={id} className="flex items-center gap-1.5 text-xs font-medium vf-text-2">
                <Icon className="h-3.5 w-3.5 vf-text-m" />
                {label}
                {required && <span className="text-red-400 ml-0.5">*</span>}
              </label>
              <input
                id={id}
                type={type}
                required={required}
                min={id === "payment_terms_days" ? "0" : undefined}
                max={id === "payment_terms_days" ? "365" : undefined}
                value={form[id]}
                onChange={e => set(id, e.target.value)}
                placeholder={placeholder}
                className="vf-input w-full"
              />
            </div>
          ))}
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-start gap-2.5 rounded-xl px-4 py-3 text-sm text-red-400 bg-red-500/[0.08] border border-red-500/20">
            <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 pt-2 border-t border-[var(--vf-divider)]">
          <Link href="/customers" className="vf-btn-ghost text-sm">
            Cancel
          </Link>
          <button
            type="submit"
            disabled={saving}
            className="vf-btn disabled:opacity-50"
          >
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            {saving ? "Creating…" : "Create customer"}
          </button>
        </div>
      </form>
    </div>
  );
}
