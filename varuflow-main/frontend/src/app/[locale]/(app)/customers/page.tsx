"use client";

import { api } from "@/lib/api-client";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { cx } from "@/lib/cx";
import styles from "./page.module.scss";
import {
  Building2, FileDown, Mail, Phone, MessageCircle, Plus, Search, FileText, ArrowRight, X,
  Hash, Globe, MapPin, Clock, AlertCircle, Users,
} from "lucide-react";
import { Link } from "@/i18n/navigation";
import { EmptyState } from "@/components/ui/EmptyState";
import ContentPanel from "@/components/console/ContentPanel";
import { EmptyCustomers } from "@/components/illustrations";

interface Customer {
  id: string;
  company_name: string;
  org_number: string | null;
  vat_number: string | null;
  email: string | null;
  phone: string | null;
  whatsapp_number: string | null;
  address: string | null;
  payment_terms_days: number;
  is_active: boolean;
}

const EMPTY = {
  company_name: "", org_number: "", vat_number: "",
  email: "", phone: "", whatsapp_number: "",
  address: "", payment_terms_days: "30",
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
  { id: "whatsapp_number", label: "WhatsApp",   icon: MessageCircle, span: false, required: false, placeholder: "+46 70 123 45 67" },
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
  const [exporting, setExporting] = useState(false);
  const [selected, setSelected]   = useState<Customer | null>(null);

  async function load() {
    try { setCustomers(await api.get<Customer[]>("/api/invoicing/customers?is_active=true")); }
    catch (e: unknown) { toast.error((e as Error).message); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  function set(f: string, v: string) { setForm(s => ({ ...s, [f]: v })); }

  async function handleExportExcel() {
    setExporting(true);
    try {
      const today = new Date().toISOString().slice(0, 10).replace(/-/g, "");
      await api.downloadBlob("/api/reports/excel/customers", `customers_${today}.xlsx`);
    } catch (e: unknown) { toast.error((e as Error).message); }
    finally { setExporting(false); }
  }

  function openCreate() {
    setEditing(null); setForm({ ...EMPTY }); setFormError(null); setOpen(true);
  }
  function openEdit(c: Customer) {
    setEditing(c);
    setForm({
      company_name: c.company_name, org_number: c.org_number ?? "",
      vat_number: c.vat_number ?? "", email: c.email ?? "",
      phone: c.phone ?? "", whatsapp_number: c.whatsapp_number ?? "",
      address: c.address ?? "",
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
        whatsapp_number:    form.whatsapp_number || null,
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
        <div className="flex items-center gap-2">
          <button
            onClick={handleExportExcel}
            disabled={exporting}
            className="vf-btn-ghost text-xs disabled:opacity-50"
            title="Download as Excel"
          >
            <FileDown className="h-3.5 w-3.5" />
            {exporting ? "Exporting…" : "Excel"}
          </button>
          <Link
            href={"/customers/segments" as Parameters<typeof Link>[0]["href"]}
            className="vf-btn-secondary text-xs"
          >
            <Users className="h-3.5 w-3.5" />Segments
          </Link>
          <Link
            href={"/campaigns" as Parameters<typeof Link>[0]["href"]}
            className="vf-btn-secondary text-xs"
          >
            <Mail className="h-3.5 w-3.5" />Campaigns
          </Link>
          <button onClick={openCreate} className="vf-btn text-xs">
            <Plus className="h-3.5 w-3.5" />New customer
          </button>
        </div>
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

      {/* ── Customer list — ContentPanel (shadcn Table + detail Sheet) ── */}
      {!loading && filtered.length === 0 ? (
        <EmptyState
          illustration={<EmptyCustomers />}
          title={search ? "No customers match your search" : "No customers yet"}
          description={search ? "Try a different search term" : "Add your first customer to start invoicing."}
          action={!search ? (
            <button onClick={openCreate} className="inline-flex vf-btn text-xs">
              <Plus className="h-3.5 w-3.5" />Add customer
            </button>
          ) : undefined}
        />
      ) : (
        <div className="vf-section overflow-hidden rounded-xl p-0">
          <ContentPanel<Customer>
            hideHeader
            title="Customers"
            rows={filtered}
            loading={loading}
            getRowId={(c) => c.id}
            columns={[
              {
                key: "company_name",
                header: "Company",
                render: (c) => (
                  <div className="flex items-center gap-2.5">
                    <Avatar name={c.company_name} />
                    <span className="font-medium text-foreground">{c.company_name}</span>
                  </div>
                ),
              },
              { key: "email", header: "Email", render: (c) => c.email ?? "—" },
              { key: "phone", header: "Phone", render: (c) => c.phone ?? "—" },
              { key: "org_number", header: "Org number", render: (c) => c.org_number ?? "—" },
              { key: "payment_terms_days", header: "Terms", render: (c) => `Net ${c.payment_terms_days}d` },
            ]}
            selected={selected}
            onSelect={setSelected}
            detailTitle={(c) => c.company_name}
            renderDetail={(c) => (
              <div className="space-y-4">
                <dl className="divide-y">
                  {([
                    ["Email", c.email],
                    ["Phone", c.phone],
                    ["Org number", c.org_number],
                    ["VAT", c.vat_number],
                    ["Address", c.address],
                    ["Payment terms", `Net ${c.payment_terms_days}d`],
                  ] as [string, string | null][]).map(([label, val]) => (
                    <div key={label} className="grid grid-cols-3 gap-2 py-2.5">
                      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
                      <dd className="col-span-2 text-sm text-foreground">{val || "—"}</dd>
                    </div>
                  ))}
                </dl>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => { setSelected(null); openEdit(c); }}
                    className="vf-btn-secondary text-xs"
                  >
                    Edit
                  </button>
                  <Link
                    href={`/invoices/new?customer=${c.id}` as Parameters<typeof Link>[0]["href"]}
                    className="vf-btn text-xs"
                  >
                    <FileText className="h-3 w-3" />New invoice
                  </Link>
                  <Link
                    href={`/invoices?customer=${c.id}` as Parameters<typeof Link>[0]["href"]}
                    className="vf-btn-ghost text-xs"
                  >
                    History <ArrowRight className="h-3 w-3" />
                  </Link>
                </div>
              </div>
            )}
          />
        </div>
      )}

      {/* ── Create / Edit modal ────────────────────────────────────── */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          className="sm:max-w-[480px] rounded-2xl border-[var(--vf-border)] bg-[var(--vf-bg-surface)]"
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
              <div className={styles.errorBanner}>
                <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                <span>{formError}</span>
              </div>
            )}

            <div className={cx("flex justify-end gap-2 pt-2", styles.divider)}>
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
