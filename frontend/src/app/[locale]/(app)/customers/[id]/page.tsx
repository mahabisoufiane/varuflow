"use client";

import { api } from "@/lib/api-client";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useLocale } from "next-intl";
import { Link } from "@/i18n/navigation";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  ArrowLeft, Building2, Mail, Phone, MessageCircle, MapPin,
  Hash, Globe, Clock, FileText, Plus, Edit2, ToggleLeft, ToggleRight,
} from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

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
  created_at: string;
}

interface Invoice {
  id: string;
  invoice_number: string;
  status: string;
  issue_date: string;
  due_date: string;
  total_sek: string;
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT:   "bg-gray-100 text-gray-600",
  SENT:    "bg-blue-100 text-blue-700",
  PAID:    "bg-emerald-100 text-emerald-700",
  OVERDUE: "bg-red-100 text-red-700",
};

const AVATAR_COLORS = [
  "from-indigo-500 to-violet-600",
  "from-emerald-500 to-teal-600",
  "from-violet-500 to-purple-600",
  "from-amber-500 to-orange-600",
  "from-rose-500 to-pink-600",
  "from-cyan-500 to-blue-600",
];

function Avatar({ name, size = "lg" }: { name: string; size?: "lg" | "sm" }) {
  const initials = name.split(" ").slice(0, 2).map(w => w[0]).join("").toUpperCase();
  const color = AVATAR_COLORS[name.charCodeAt(0) % AVATAR_COLORS.length];
  const cls = size === "lg"
    ? "h-14 w-14 text-xl rounded-2xl"
    : "h-10 w-10 text-sm rounded-xl";
  return (
    <div className={cn("flex shrink-0 items-center justify-center bg-gradient-to-br font-bold text-white select-none", cls, color)}>
      {initials}
    </div>
  );
}

const EDIT_FIELDS = [
  { id: "company_name",        label: "Company name",         span: true,  type: "text",   required: true },
  { id: "org_number",          label: "Org number",           span: false, type: "text",   required: false },
  { id: "vat_number",          label: "VAT number",           span: false, type: "text",   required: false },
  { id: "email",               label: "Email",                span: false, type: "email",  required: false },
  { id: "phone",               label: "Phone",                span: false, type: "tel",    required: false },
  { id: "address",             label: "Address",              span: true,  type: "text",   required: false },
  { id: "payment_terms_days",  label: "Payment terms (days)", span: false, type: "number", required: false },
] as const;

export default function CustomerDetailPage() {
  const params   = useParams<{ id: string }>();
  const router   = useRouter();
  const locale   = useLocale();

  const [customer, setCustomer]   = useState<Customer | null>(null);
  const [invoices, setInvoices]   = useState<Invoice[]>([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [editOpen, setEditOpen]   = useState(false);
  const [form, setForm]           = useState<Record<string, string>>({});
  const [saving, setSaving]       = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deactivating, setDeactivating] = useState(false);

  async function load() {
    try {
      const [cust, invs] = await Promise.all([
        api.get<Customer>(`/api/invoicing/customers/${params.id}`),
        api.get<Invoice[]>(`/api/invoicing/invoices?customer_id=${params.id}`),
      ]);
      setCustomer(cust);
      setInvoices(invs);
    } catch (e: unknown) {
      const msg = (e as Error).message;
      setError(msg);
      if (msg.includes("session")) router.push(`/${locale}/auth/login`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [params.id]);

  function openEdit() {
    if (!customer) return;
    setForm({
      company_name:       customer.company_name,
      org_number:         customer.org_number ?? "",
      vat_number:         customer.vat_number ?? "",
      email:              customer.email ?? "",
      phone:              customer.phone ?? "",
      address:            customer.address ?? "",
      payment_terms_days: String(customer.payment_terms_days),
    });
    setFormError(null);
    setEditOpen(true);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setFormError(null);
    try {
      await api.put(`/api/invoicing/customers/${params.id}`, {
        company_name:       form.company_name,
        org_number:         form.org_number || null,
        vat_number:         form.vat_number || null,
        email:              form.email || null,
        phone:              form.phone || null,
        address:            form.address || null,
        payment_terms_days: Number(form.payment_terms_days) || 30,
      });
      toast.success("Customer updated");
      setEditOpen(false);
      await load();
    } catch (e: unknown) {
      setFormError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleActive() {
    if (!customer) return;
    setDeactivating(true);
    try {
      await api.delete(`/api/invoicing/customers/${params.id}`);
      toast.success(customer.is_active ? "Customer deactivated" : "Customer updated");
      await load();
    } catch (e: unknown) {
      toast.error((e as Error).message);
    } finally {
      setDeactivating(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 skeleton rounded-lg" />
        <div className="h-32 skeleton rounded-2xl" />
        <div className="h-64 skeleton rounded-2xl" />
      </div>
    );
  }

  if (error || !customer) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4">
        <p className="text-sm vf-text-m">
          {error ?? "Customer not found."}
        </p>
        <Link
          href={"/customers" as Parameters<typeof Link>[0]["href"]}
          className="vf-btn text-xs"
        >
          Back to customers
        </Link>
      </div>
    );
  }

  const totalRevenue = invoices
    .filter(i => i.status === "PAID")
    .reduce((sum, i) => sum + parseFloat(i.total_sek || "0"), 0);

  return (
    <div className="space-y-6">

      {/* ── Back nav ───────────────────────────────────────────────────── */}
      <Link
        href={"/customers" as Parameters<typeof Link>[0]["href"]}
        className="inline-flex items-center gap-1.5 text-xs vf-text-m hover:vf-text-2 transition-colors"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        All customers
      </Link>

      {/* ── Header card ────────────────────────────────────────────────── */}
      <div className="vf-section p-6 rounded-2xl flex items-start gap-5">
        <Avatar name={customer.company_name} />

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h1 className="text-xl font-bold vf-text-1 leading-tight">{customer.company_name}</h1>
              <span
                className={cn(
                  "inline-block mt-1 rounded-full px-2 py-0.5 text-[10px] font-semibold",
                  customer.is_active ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500"
                )}
              >
                {customer.is_active ? "Active" : "Inactive"}
              </span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={handleToggleActive}
                disabled={deactivating}
                className="vf-btn-ghost h-8 px-3 text-xs flex items-center gap-1.5"
              >
                {customer.is_active
                  ? <><ToggleRight className="h-4 w-4 text-emerald-500" />Deactivate</>
                  : <><ToggleLeft className="h-4 w-4" />Activate</>
                }
              </button>
              <button
                onClick={openEdit}
                className="vf-btn-secondary h-8 px-3 text-xs flex items-center gap-1.5"
              >
                <Edit2 className="h-3.5 w-3.5" />Edit
              </button>
              <Link
                href={`/invoices/new?customer=${customer.id}` as Parameters<typeof Link>[0]["href"]}
                className="vf-btn h-8 px-3 text-xs flex items-center gap-1.5"
              >
                <Plus className="h-3.5 w-3.5" />New invoice
              </Link>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
            {customer.email && (
              <div className="flex items-center gap-2 text-xs vf-text-m">
                <Mail className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{customer.email}</span>
              </div>
            )}
            {customer.phone && (
              <div className="flex items-center gap-2 text-xs vf-text-m">
                <Phone className="h-3.5 w-3.5 shrink-0" />{customer.phone}
              </div>
            )}
            {customer.org_number && (
              <div className="flex items-center gap-2 text-xs vf-text-m">
                <Building2 className="h-3.5 w-3.5 shrink-0" />Org {customer.org_number}
              </div>
            )}
            {customer.vat_number && (
              <div className="flex items-center gap-2 text-xs vf-text-m">
                <Globe className="h-3.5 w-3.5 shrink-0" />{customer.vat_number}
              </div>
            )}
            {customer.address && (
              <div className="flex items-center gap-2 text-xs vf-text-m col-span-2">
                <MapPin className="h-3.5 w-3.5 shrink-0" />{customer.address}
              </div>
            )}
            <div className="flex items-center gap-2 text-xs vf-text-m">
              <Clock className="h-3.5 w-3.5 shrink-0" />Net {customer.payment_terms_days} days
            </div>
            <div className="flex items-center gap-2 text-xs vf-text-m">
              <Hash className="h-3.5 w-3.5 shrink-0" />
              Since {new Date(customer.created_at).toLocaleDateString("sv-SE")}
            </div>
          </div>
        </div>
      </div>

      {/* ── Stats ──────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Total invoices",  value: invoices.length },
          { label: "Paid invoices",   value: invoices.filter(i => i.status === "PAID").length },
          { label: "Total revenue",   value: `${totalRevenue.toLocaleString("sv-SE")} kr` },
        ].map(({ label, value }) => (
          <div key={label} className="vf-section rounded-xl p-4">
            <p className="text-xs vf-text-m">{label}</p>
            <p className="text-lg font-bold vf-text-1 mt-0.5">{value}</p>
          </div>
        ))}
      </div>

      {/* ── Invoice history ─────────────────────────────────────────────── */}
      <div className="vf-section rounded-2xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: "var(--vf-border)" }}>
          <h2 className="text-sm font-semibold vf-text-1 flex items-center gap-2">
            <FileText className="h-4 w-4" />Invoice history
          </h2>
          <Link
            href={`/invoices/new?customer=${customer.id}` as Parameters<typeof Link>[0]["href"]}
            className="text-xs vf-text-m hover:text-indigo-500 transition-colors flex items-center gap-1"
          >
            <Plus className="h-3 w-3" />New invoice
          </Link>
        </div>

        {invoices.length === 0 ? (
          <div className="py-12 text-center">
            <p className="text-sm vf-text-m">No invoices yet for this customer.</p>
          </div>
        ) : (
          <div className="divide-y" style={{ borderColor: "var(--vf-border)" }}>
            {invoices.map(inv => (
              <Link
                key={inv.id}
                href={`/invoices/${inv.id}` as Parameters<typeof Link>[0]["href"]}
                className="flex items-center justify-between px-5 py-3 hover:bg-[var(--vf-bg-elevated)] transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold", STATUS_COLORS[inv.status] ?? "bg-gray-100 text-gray-600")}>
                    {inv.status}
                  </span>
                  <span className="text-sm font-medium vf-text-1">{inv.invoice_number}</span>
                  <span className="text-xs vf-text-m">{inv.issue_date}</span>
                </div>
                <span className="text-sm font-semibold vf-text-1">
                  {parseFloat(inv.total_sek).toLocaleString("sv-SE")} kr
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* ── Edit modal ─────────────────────────────────────────────────── */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent
          className="sm:max-w-[480px]"
          style={{ background: "var(--vf-bg-surface)", borderColor: "var(--vf-border)", borderRadius: 16 }}
        >
          <DialogHeader>
            <DialogTitle className="vf-text-1 text-base font-semibold">
              Edit {customer.company_name}
            </DialogTitle>
          </DialogHeader>

          <form onSubmit={handleSave} className="space-y-4 pt-1">
            <div className="grid grid-cols-2 gap-3">
              {EDIT_FIELDS.map(({ id, label, span, type, required }) => (
                <div key={id} className={cn("space-y-1.5", span ? "col-span-2" : "")}>
                  <label htmlFor={`edit-${id}`} className="text-xs font-medium vf-text-2">
                    {label}
                  </label>
                  <input
                    id={`edit-${id}`}
                    type={type}
                    required={required}
                    min={id === "payment_terms_days" ? "0" : undefined}
                    max={id === "payment_terms_days" ? "365" : undefined}
                    value={form[id] ?? ""}
                    onChange={e => setForm(s => ({ ...s, [id]: e.target.value }))}
                    className="vf-input w-full"
                  />
                </div>
              ))}
            </div>

            {formError && (
              <p className="text-xs text-red-500 rounded-lg px-3 py-2 bg-red-50">{formError}</p>
            )}

            <div className="flex justify-end gap-2 pt-1">
              <button type="button" onClick={() => setEditOpen(false)} className="vf-btn-ghost text-sm h-9 px-4">
                Cancel
              </button>
              <button type="submit" disabled={saving} className="vf-btn text-sm h-9 px-4">
                {saving ? "Saving…" : "Save changes"}
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

    </div>
  );
}
