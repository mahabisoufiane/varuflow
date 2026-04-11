"use client";

import { api } from "@/lib/api-client";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  Building2, Mail, Phone, Plus, Search, FileText, ArrowRight, X,
  Hash, Globe, MapPin, Clock, AlertCircle, Users,
} from "lucide-react";
import { Link } from "@/i18n/navigation";

interface Customer {
  id: string;
  company_name: string;
  org_number: string | null;
  vat_number: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  payment_terms_days: number;
  is_active: boolean;
}

const EMPTY = {
  company_name: "", org_number: "", vat_number: "",
  email: "", phone: "", address: "", payment_terms_days: "30",
};

const AVATAR_COLORS = [
  "from-indigo-500 to-violet-600",
  "from-emerald-500 to-teal-600",
  "from-violet-500 to-purple-600",
  "from-amber-500 to-orange-600",
  "from-rose-500 to-pink-600",
  "from-cyan-500 to-blue-600",
];

function Avatar({ name }: { name: string }) {
  const initials = name.split(" ").slice(0, 2).map(w => w[0]).join("").toUpperCase();
  const color = AVATAR_COLORS[name.charCodeAt(0) % AVATAR_COLORS.length];
  return (
    <div className={cn(
      "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br text-[13px] font-bold text-white select-none",
      color
    )}>
      {initials}
    </div>
  );
}

const FORM_FIELDS = [
  { id: "company_name", label: "Company name *", icon: Building2, span: true,  required: true,  placeholder: "Nordisk Handel AB"     },
  { id: "org_number",   label: "Org number",     icon: Hash,      span: false, required: false, placeholder: "556123-4567"            },
  { id: "vat_number",   label: "VAT number",     icon: Globe,     span: false, required: false, placeholder: "SE556123456701"         },
  { id: "email",        label: "Email",          icon: Mail,      span: false, required: false, placeholder: "orders@company.se"      },
  { id: "phone",        label: "Phone",          icon: Phone,     span: false, required: false, placeholder: "+46 8 123 456"          },
  { id: "address",      label: "Address",        icon: MapPin,    span: true,  required: false, placeholder: "Storgatan 1, Stockholm" },
  { id: "payment_terms_days", label: "Payment terms (days)", icon: Clock, span: false, required: false, placeholder: "30" },
] as const;

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading]     = useState(true);
  const [search, setSearch]       = useState("");
  const [open, setOpen]           = useState(false);
  const [editing, setEditing]     = useState<Customer | null>(null);
  const [form, setForm]           = useState({ ...EMPTY });
  const [saving, setSaving]       = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function load() {
    try { setCustomers(await api.get<Customer[]>("/api/invoicing/customers?is_active=true")); }
    catch (e: unknown) { toast.error((e as Error).message); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  function set(f: string, v: string) { setForm(s => ({ ...s, [f]: v })); }

  function openCreate() {
    setEditing(null); setForm({ ...EMPTY }); setFormError(null); setOpen(true);
  }
  function openEdit(c: Customer) {
    setEditing(c);
    setForm({
      company_name: c.company_name, org_number: c.org_number ?? "",
      vat_number: c.vat_number ?? "", email: c.email ?? "",
      phone: c.phone ?? "", address: c.address ?? "",
      payment_terms_days: String(c.payment_terms_days),
    });
    setFormError(null); setOpen(true);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault(); setSaving(true); setFormError(null);
    try {
      const body = {
        company_name:       form.company_name,
        org_number:         form.org_number || null,
        vat_number:         form.vat_number || null,
        email:              form.email || null,
        phone:              form.phone || null,
        address:            form.address || null,
        payment_terms_days: Number(form.payment_terms_days),
      };
      if (editing) await api.put(`/api/invoicing/customers/${editing.id}`, body);
      else         await api.post("/api/invoicing/customers", body);
      toast.success(editing ? "Customer updated" : "Customer created");
      setOpen(false); await load();
    } catch (e: unknown) { setFormError((e as Error).message); }
    finally { setSaving(false); }
  }

  const filtered = customers.filter(c =>
    c.company_name.toLowerCase().includes(search.toLowerCase()) ||
    (c.email ?? "").toLowerCase().includes(search.toLowerCase()) ||
    (c.org_number ?? "").includes(search)
  );

  return (
    <div className="space-y-6">

      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight vf-text-1">Customers</h1>
          <p className="text-xs vf-text-m mt-0.5">{customers.length} active customers</p>
        </div>
        <button onClick={openCreate} className="vf-btn text-xs">
          <Plus className="h-3.5 w-3.5" />New customer
        </button>
      </div>

      {/* ── Search ─────────────────────────────────────────────────── */}
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 vf-text-m" />
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search by name, email, or org number…"
          className="vf-input pl-9 pr-9 w-full"
        />
        {search && (
          <button
            onClick={() => setSearch("")}
            className="absolute right-3 top-1/2 -translate-y-1/2 vf-text-m hover:vf-text-2 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* ── Customer grid ──────────────────────────────────────────── */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[1, 2, 3, 4].map(i => <div key={i} className="h-28 skeleton rounded-xl" />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl px-6 py-20 text-center"
          style={{ border: "1px dashed var(--vf-border-strong)", background: "var(--vf-bg-surface)" }}>
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl"
            style={{ background: "var(--vf-bg-elevated)" }}>
            <Users className="h-6 w-6 vf-text-m" />
          </div>
          <p className="text-sm font-semibold vf-text-2">
            {search ? "No customers match your search" : "No customers yet"}
          </p>
          <p className="text-xs vf-text-m mt-1">
            {search ? "Try a different search term" : "Add your first customer to start invoicing."}
          </p>
          {!search && (
            <button onClick={openCreate} className="mt-5 inline-flex vf-btn text-xs">
              <Plus className="h-3.5 w-3.5" />Add customer
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {filtered.map(c => (
            <div
              key={c.id}
              className="group vf-section flex items-start gap-4 p-5 hover:shadow-card transition-all"
              style={{ borderRadius: 14 }}
              onMouseEnter={e => (e.currentTarget.style.background = "var(--vf-bg-elevated)")}
              onMouseLeave={e => (e.currentTarget.style.background = "var(--vf-bg-surface)")}
            >
              <Avatar name={c.company_name} />

              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <p className="font-semibold vf-text-1 leading-tight truncate">{c.company_name}</p>
                  <span className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold vf-text-m"
                    style={{ background: "var(--vf-bg-elevated)", border: "1px solid var(--vf-border-strong)" }}>
                    Net {c.payment_terms_days}d
                  </span>
                </div>

                <div className="mt-2 space-y-1">
                  {c.email && (
                    <div className="flex items-center gap-1.5 text-xs vf-text-m">
                      <Mail className="h-3 w-3 shrink-0" />{c.email}
                    </div>
                  )}
                  {c.phone && (
                    <div className="flex items-center gap-1.5 text-xs vf-text-m">
                      <Phone className="h-3 w-3 shrink-0" />{c.phone}
                    </div>
                  )}
                  {c.org_number && (
                    <div className="flex items-center gap-1.5 text-xs vf-text-m">
                      <Building2 className="h-3 w-3 shrink-0" />Org {c.org_number}
                    </div>
                  )}
                </div>

                <div className="mt-3 flex items-center gap-2">
                  <button
                    onClick={() => openEdit(c)}
                    className="vf-btn-ghost h-7 px-2.5 text-[11px] font-semibold"
                  >
                    Edit
                  </button>
                  <Link
                    href={`/invoices/new?customer=${c.id}` as Parameters<typeof Link>[0]["href"]}
                    className="inline-flex items-center gap-1 rounded-lg px-2.5 h-7 text-[11px] font-semibold text-indigo-500 transition-colors"
                    style={{ background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.2)" }}
                  >
                    <FileText className="h-3 w-3" />Invoice
                  </Link>
                  <Link
                    href={`/invoices?customer=${c.id}` as Parameters<typeof Link>[0]["href"]}
                    className="ml-auto inline-flex items-center gap-1 text-[11px] vf-text-m hover:text-indigo-500 transition-colors"
                  >
                    History <ArrowRight className="h-3 w-3" />
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Create / Edit modal ────────────────────────────────────── */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          className="sm:max-w-[480px]"
          style={{ background: "var(--vf-bg-surface)", borderColor: "var(--vf-border)", borderRadius: 16 }}
        >
          <DialogHeader>
            <DialogTitle className="vf-text-1 text-base font-semibold">
              {editing ? `Edit ${editing.company_name}` : "New customer"}
            </DialogTitle>
          </DialogHeader>

          <form onSubmit={handleSave} className="space-y-4 pt-1">
            <div className="grid grid-cols-2 gap-3">
              {FORM_FIELDS.map(({ id, label, icon: Icon, span, required, placeholder }) => (
                <div key={id} className={cn("space-y-1.5", span ? "col-span-2" : "")}>
                  <label htmlFor={id} className="flex items-center gap-1.5 text-xs font-medium vf-text-2">
                    <Icon className="h-3 w-3 vf-text-m" />
                    {label}
                  </label>
                  <input
                    id={id}
                    type={id === "payment_terms_days" ? "number" : "text"}
                    required={required}
                    min={id === "payment_terms_days" ? "0" : undefined}
                    max={id === "payment_terms_days" ? "365" : undefined}
                    value={(form as Record<string, string>)[id]}
                    onChange={e => set(id, e.target.value)}
                    placeholder={placeholder}
                    className="vf-input w-full"
                  />
                </div>
              ))}
            </div>

            {formError && (
              <div className="flex items-start gap-2.5 rounded-xl px-3.5 py-2.5 text-sm text-red-400"
                style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)" }}>
                <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                <span>{formError}</span>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2" style={{ borderTop: "1px solid var(--vf-divider)" }}>
              <button type="button" onClick={() => setOpen(false)} className="vf-btn-ghost text-xs px-4">
                Cancel
              </button>
              <button type="submit" disabled={saving} className="vf-btn text-xs px-4 disabled:opacity-50">
                {saving ? "Saving…" : editing ? "Save changes" : "Create customer"}
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
