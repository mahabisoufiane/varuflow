"use client";

import { createClient } from "@/lib/supabase/client";
import { useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Check, Building2, DollarSign, Package, Users, UserPlus, Link2, PartyPopper } from "lucide-react";

// Swedish org number: 6 digits, optional dash, 4 digits
const ORG_NUMBER_RE = /^\d{6}-?\d{4}$/;

type StepKey = 1 | 2 | 3 | 4 | 5 | 6 | 7;

const STEPS: { step: StepKey; label: string; icon: React.ElementType }[] = [
  { step: 1, label: "Company",    icon: Building2   },
  { step: 2, label: "Finance",    icon: DollarSign  },
  { step: 3, label: "Product",    icon: Package     },
  { step: 4, label: "Customer",   icon: Users       },
  { step: 5, label: "Team",       icon: UserPlus    },
  { step: 6, label: "Accounting", icon: Link2       },
  { step: 7, label: "Done",       icon: PartyPopper },
];

const CURRENCIES = ["SEK", "NOK", "DKK", "EUR", "USD", "GBP"];
const MONTHS = [
  "January","February","March","April","May","June",
  "July","August","September","October","November","December",
];

export default function OnboardingPage() {
  const t = useTranslations("onboarding");
  const router = useRouter();
  const searchParams = useSearchParams();
  const plan = searchParams.get("plan") ?? "";
  const supabase = createClient();

  const [step, setStep] = useState<StepKey>(1);
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  // Step 1 — company profile
  const [company, setCompany] = useState({ company_name: "", org_number: "", vat_number: "", address: "" });
  const [companyErrors, setCompanyErrors] = useState<Partial<typeof company>>({});

  // Step 2 — currency & fiscal year
  const [currency, setCurrency] = useState("SEK");
  const [fiscalStart, setFiscalStart] = useState(1);

  // Step 3 — first product
  const [product, setProduct] = useState({ name: "", sku: "", sell_price: "", tax_rate: "25" });
  const [productSaved, setProductSaved] = useState(false);

  // Step 4 — first customer
  const [customer, setCustomer] = useState({ company_name: "", email: "", org_number: "" });
  const [customerSaved, setCustomerSaved] = useState(false);

  // Step 5 — invite team member
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [inviteSent, setInviteSent] = useState(false);

  async function getToken(): Promise<string | null> {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token ?? null;
  }

  function apiUrl(path: string) {
    return `${process.env.NEXT_PUBLIC_API_URL}${path}`;
  }

  // ── Step 1 submit ────────────────────────────────────────────────────────────
  async function handleCompanySubmit(e: React.FormEvent) {
    e.preventDefault();
    const errs: Partial<typeof company> = {};
    if (!company.company_name.trim()) errs.company_name = "Required";
    if (company.org_number && !ORG_NUMBER_RE.test(company.org_number)) errs.org_number = "Format: 556000-0000";
    if (Object.keys(errs).length) { setCompanyErrors(errs); return; }

    setLoading(true);
    setApiError(null);
    try {
      const token = await getToken();
      if (!token) { router.push("/auth/login"); return; }

      const res = await fetch(apiUrl("/api/auth/onboarding"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          company_name: company.company_name,
          org_number: company.org_number || null,
          vat_number: company.vat_number || null,
          address: company.address || null,
        }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail ?? "Failed to save company");
      }
      setStep(2);
    } catch (err) {
      setApiError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  // ── Step 2 submit ────────────────────────────────────────────────────────────
  async function handleFinanceSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setApiError(null);
    try {
      const token = await getToken();
      if (!token) { router.push("/auth/login"); return; }

      const res = await fetch(apiUrl("/api/onboarding/wizard/org-setup"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          company_name: company.company_name,
          base_currency: currency,
          fiscal_year_start: fiscalStart,
        }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail ?? "Failed to save settings");
      }
      setStep(3);
    } catch (err) {
      setApiError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  // ── Step 3 — create first product ───────────────────────────────────────────
  async function handleProductSave() {
    if (!product.name.trim()) { setApiError("Product name is required"); return; }
    setLoading(true);
    setApiError(null);
    try {
      const token = await getToken();
      if (!token) { router.push("/auth/login"); return; }
      const res = await fetch(apiUrl("/api/inventory/products"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          name: product.name,
          sku: product.sku || null,
          sell_price: parseFloat(product.sell_price) || 0,
          tax_rate: parseFloat(product.tax_rate) || 25,
        }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail ?? "Failed to create product");
      }
      setProductSaved(true);
    } catch (err) {
      setApiError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  // ── Step 4 — create first customer ──────────────────────────────────────────
  async function handleCustomerSave() {
    if (!customer.company_name.trim()) { setApiError("Company name is required"); return; }
    setLoading(true);
    setApiError(null);
    try {
      const token = await getToken();
      if (!token) { router.push("/auth/login"); return; }
      const res = await fetch(apiUrl("/api/invoicing/customers"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          company_name: customer.company_name,
          email: customer.email || null,
          org_number: customer.org_number || null,
        }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail ?? "Failed to create customer");
      }
      setCustomerSaved(true);
    } catch (err) {
      setApiError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  // ── Step 5 — invite team member ──────────────────────────────────────────────
  async function handleInvite() {
    if (!inviteEmail.trim()) { setApiError("Email is required"); return; }
    setLoading(true);
    setApiError(null);
    try {
      const token = await getToken();
      if (!token) { router.push("/auth/login"); return; }
      const res = await fetch(apiUrl("/api/team/invite"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ email: inviteEmail, role: inviteRole }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail ?? "Failed to send invite");
      }
      setInviteSent(true);
    } catch (err) {
      setApiError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  // ── Finish wizard ────────────────────────────────────────────────────────────
  async function finishWizard() {
    setLoading(true);
    try {
      const token = await getToken();
      if (!token) { router.push("/auth/login"); return; }
      await fetch(apiUrl("/api/onboarding/wizard/complete"), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });

      if (plan === "starter" || plan === "professional") {
        const res = await fetch(apiUrl("/api/billing/checkout"), {
          method: "POST",
          headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
          body: JSON.stringify({ plan }),
        });
        if (res.ok) {
          const { url } = await res.json();
          window.location.href = url;
          return;
        }
      }
    } catch {}
    router.push("/dashboard");
  }

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-12">
      <div className="w-full max-w-lg">

        {/* Header */}
        <div className="mb-8 text-center">
          <span className="text-2xl font-bold text-[#1a2332]">Varuflow</span>
          <h1 className="mt-4 text-xl font-semibold text-gray-900">{t("title")}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>

        {/* Step indicators */}
        <div className="mb-8 flex items-center justify-center gap-1">
          {STEPS.map(({ step: s, label }) => (
            <div key={s} className="flex items-center gap-1">
              <div
                className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium transition-colors ${
                  s === step
                    ? "bg-[#1a2332] text-white"
                    : s < step
                    ? "bg-green-500 text-white"
                    : "border border-gray-300 text-gray-400"
                }`}
                title={label}
              >
                {s < step ? <Check className="h-3.5 w-3.5" /> : s}
              </div>
              {s < 7 && <div className={`h-px w-4 ${s < step ? "bg-green-500" : "bg-gray-200"}`} />}
            </div>
          ))}
        </div>

        {/* Error banner */}
        {apiError && (
          <div className="mb-4 rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {apiError}
          </div>
        )}

        {/* ── Step 1: Company Profile ── */}
        {step === 1 && (
          <form onSubmit={handleCompanySubmit} className="space-y-5 rounded-xl border bg-white p-8 shadow-sm">
            <div className="flex items-center gap-2">
              <Building2 className="h-5 w-5 text-[#1a2332]" />
              <h2 className="text-base font-semibold text-gray-900">{t("step1Title")}</h2>
            </div>

            <Field
              id="company_name" label={t("companyName")} required
              placeholder={t("companyNamePlaceholder")}
              value={company.company_name} error={companyErrors.company_name}
              onChange={(v) => setCompany((f) => ({ ...f, company_name: v }))}
            />
            <Field
              id="org_number" label={t("orgNumber")}
              placeholder={t("orgNumberPlaceholder")} hint={t("orgNumberHint")}
              value={company.org_number} error={companyErrors.org_number}
              onChange={(v) => setCompany((f) => ({ ...f, org_number: v }))}
            />
            <Field
              id="vat_number" label={t("vatNumber")}
              placeholder={t("vatNumberPlaceholder")}
              value={company.vat_number}
              onChange={(v) => setCompany((f) => ({ ...f, vat_number: v }))}
            />
            <Field
              id="address" label={t("address")}
              placeholder="Storgatan 1, 111 23 Stockholm"
              value={company.address}
              onChange={(v) => setCompany((f) => ({ ...f, address: v }))}
            />

            <Button type="submit" disabled={loading} className="w-full bg-[#1a2332] hover:bg-[#2a3342] text-white">
              {loading ? "Saving…" : t("continue")}
            </Button>
          </form>
        )}

        {/* ── Step 2: Currency & Fiscal Year ── */}
        {step === 2 && (
          <form onSubmit={handleFinanceSubmit} className="space-y-5 rounded-xl border bg-white p-8 shadow-sm">
            <div className="flex items-center gap-2">
              <DollarSign className="h-5 w-5 text-[#1a2332]" />
              <h2 className="text-base font-semibold text-gray-900">Currency & Fiscal Year</h2>
            </div>
            <p className="text-sm text-muted-foreground">
              Choose your base currency and when your fiscal year starts. This affects VAT, reporting, and invoicing.
            </p>

            <div className="space-y-1">
              <label className="text-sm font-medium text-gray-700">Base Currency</label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-1 focus:border-[#1a2332] focus:ring-[#1a2332]"
              >
                {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-sm font-medium text-gray-700">Fiscal Year Starts</label>
              <select
                value={fiscalStart}
                onChange={(e) => setFiscalStart(parseInt(e.target.value))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-1 focus:border-[#1a2332] focus:ring-[#1a2332]"
              >
                {MONTHS.map((m, i) => <option key={i + 1} value={i + 1}>{m}</option>)}
              </select>
              <p className="text-xs text-muted-foreground">Most Swedish companies use January (month 1).</p>
            </div>

            <div className="flex gap-3">
              <Button type="button" variant="outline" className="flex-1" onClick={() => setStep(1)}>Back</Button>
              <Button type="submit" disabled={loading} className="flex-1 bg-[#1a2332] hover:bg-[#2a3342] text-white">
                {loading ? "Saving…" : "Continue"}
              </Button>
            </div>
          </form>
        )}

        {/* ── Step 3: First Product ── */}
        {step === 3 && (
          <div className="space-y-5 rounded-xl border bg-white p-8 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Package className="h-5 w-5 text-[#1a2332]" />
                <h2 className="text-base font-semibold text-gray-900">Add Your First Product</h2>
              </div>
              <span className="text-xs text-muted-foreground">Optional</span>
            </div>

            {productSaved ? (
              <div className="flex items-center gap-3 rounded-lg bg-green-50 border border-green-200 px-4 py-3">
                <Check className="h-5 w-5 text-green-600 flex-shrink-0" />
                <p className="text-sm text-green-700 font-medium">Product &ldquo;{product.name}&rdquo; added</p>
              </div>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">
                  Products appear on invoices and drive inventory tracking. You can add more later.
                </p>
                <Field id="pname" label="Product Name" required placeholder="Nordic Oak Desk"
                  value={product.name} onChange={(v) => setProduct((f) => ({ ...f, name: v }))} />
                <div className="grid grid-cols-2 gap-4">
                  <Field id="psku" label="SKU" placeholder="DESK-001"
                    value={product.sku} onChange={(v) => setProduct((f) => ({ ...f, sku: v }))} />
                  <Field id="pprice" label="Price (excl. VAT)" placeholder="4990"
                    value={product.sell_price} onChange={(v) => setProduct((f) => ({ ...f, sell_price: v }))} />
                </div>
                <div className="space-y-1">
                  <label className="text-sm font-medium text-gray-700">VAT Rate</label>
                  <select value={product.tax_rate} onChange={(e) => setProduct((f) => ({ ...f, tax_rate: e.target.value }))}
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-1 focus:border-[#1a2332] focus:ring-[#1a2332]">
                    <option value="0">0%</option>
                    <option value="6">6%</option>
                    <option value="12">12%</option>
                    <option value="25">25%</option>
                  </select>
                </div>
                <Button disabled={loading || !product.name.trim()} onClick={handleProductSave}
                  className="w-full bg-[#1a2332] hover:bg-[#2a3342] text-white">
                  {loading ? "Saving…" : "Save Product"}
                </Button>
              </>
            )}

            <div className="flex gap-3">
              <Button type="button" variant="outline" className="flex-1" onClick={() => setStep(2)}>Back</Button>
              <Button type="button" className="flex-1 bg-[#1a2332] hover:bg-[#2a3342] text-white" onClick={() => setStep(4)}>
                {productSaved ? "Continue" : "Skip for now"}
              </Button>
            </div>
          </div>
        )}

        {/* ── Step 4: First Customer ── */}
        {step === 4 && (
          <div className="space-y-5 rounded-xl border bg-white p-8 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Users className="h-5 w-5 text-[#1a2332]" />
                <h2 className="text-base font-semibold text-gray-900">Add Your First Customer</h2>
              </div>
              <span className="text-xs text-muted-foreground">Optional</span>
            </div>

            {customerSaved ? (
              <div className="flex items-center gap-3 rounded-lg bg-green-50 border border-green-200 px-4 py-3">
                <Check className="h-5 w-5 text-green-600 flex-shrink-0" />
                <p className="text-sm text-green-700 font-medium">Customer &ldquo;{customer.company_name}&rdquo; added</p>
              </div>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">Add a customer so you can create your first invoice right away.</p>
                <Field id="cname" label="Company Name" required placeholder="Bergström & Partners AB"
                  value={customer.company_name} onChange={(v) => setCustomer((f) => ({ ...f, company_name: v }))} />
                <Field id="cemail" label="Email" placeholder="faktura@example.se"
                  value={customer.email} onChange={(v) => setCustomer((f) => ({ ...f, email: v }))} />
                <Field id="corgno" label="Org Number" placeholder="556000-0000"
                  value={customer.org_number} onChange={(v) => setCustomer((f) => ({ ...f, org_number: v }))} />
                <Button disabled={loading || !customer.company_name.trim()} onClick={handleCustomerSave}
                  className="w-full bg-[#1a2332] hover:bg-[#2a3342] text-white">
                  {loading ? "Saving…" : "Save Customer"}
                </Button>
              </>
            )}

            <div className="flex gap-3">
              <Button type="button" variant="outline" className="flex-1" onClick={() => setStep(3)}>Back</Button>
              <Button type="button" className="flex-1 bg-[#1a2332] hover:bg-[#2a3342] text-white" onClick={() => setStep(5)}>
                {customerSaved ? "Continue" : "Skip for now"}
              </Button>
            </div>
          </div>
        )}

        {/* ── Step 5: Invite Team Member ── */}
        {step === 5 && (
          <div className="space-y-5 rounded-xl border bg-white p-8 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <UserPlus className="h-5 w-5 text-[#1a2332]" />
                <h2 className="text-base font-semibold text-gray-900">Invite a Team Member</h2>
              </div>
              <span className="text-xs text-muted-foreground">Optional</span>
            </div>

            {inviteSent ? (
              <div className="flex items-center gap-3 rounded-lg bg-green-50 border border-green-200 px-4 py-3">
                <Check className="h-5 w-5 text-green-600 flex-shrink-0" />
                <p className="text-sm text-green-700 font-medium">Invite sent to {inviteEmail}</p>
              </div>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">Accountants, warehouse managers, or sales staff can all have their own login.</p>
                <Field id="iemail" label="Email Address" placeholder="colleague@company.se"
                  value={inviteEmail} onChange={setInviteEmail} />
                <div className="space-y-1">
                  <label className="text-sm font-medium text-gray-700">Role</label>
                  <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)}
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-1 focus:border-[#1a2332] focus:ring-[#1a2332]">
                    <option value="admin">Admin</option>
                    <option value="member">Member</option>
                    <option value="viewer">Viewer</option>
                  </select>
                </div>
                <Button disabled={loading || !inviteEmail.trim()} onClick={handleInvite}
                  className="w-full bg-[#1a2332] hover:bg-[#2a3342] text-white">
                  {loading ? "Sending…" : "Send Invite"}
                </Button>
              </>
            )}

            <div className="flex gap-3">
              <Button type="button" variant="outline" className="flex-1" onClick={() => setStep(4)}>Back</Button>
              <Button type="button" className="flex-1 bg-[#1a2332] hover:bg-[#2a3342] text-white" onClick={() => setStep(6)}>
                {inviteSent ? "Continue" : "Skip for now"}
              </Button>
            </div>
          </div>
        )}

        {/* ── Step 6: Accounting Integration ── */}
        {step === 6 && (
          <div className="space-y-5 rounded-xl border bg-white p-8 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Link2 className="h-5 w-5 text-[#1a2332]" />
                <h2 className="text-base font-semibold text-gray-900">Connect Accounting Software</h2>
              </div>
              <span className="text-xs text-muted-foreground">Optional</span>
            </div>
            <p className="text-sm text-muted-foreground">
              Sync invoices, VAt returns, and the chart of accounts automatically. Supported: Fortnox, Visma, and more.
            </p>

            <a
              href="/settings#integrations"
              className="flex items-center justify-between rounded-lg border border-gray-200 px-4 py-3 hover:bg-gray-50 transition-colors"
            >
              <div>
                <p className="text-sm font-medium text-gray-900">Connect Fortnox</p>
                <p className="text-xs text-muted-foreground">Sweden&apos;s most popular accounting platform</p>
              </div>
              <Link2 className="h-4 w-4 text-muted-foreground" />
            </a>

            <div className="rounded-lg bg-blue-50 border border-blue-200 px-4 py-3">
              <p className="text-xs text-blue-700">
                You can connect integrations at any time from <strong>Settings → Integrations</strong>.
              </p>
            </div>

            <div className="flex gap-3">
              <Button type="button" variant="outline" className="flex-1" onClick={() => setStep(5)}>Back</Button>
              <Button type="button" className="flex-1 bg-[#1a2332] hover:bg-[#2a3342] text-white" onClick={() => setStep(7)}>
                Continue
              </Button>
            </div>
          </div>
        )}

        {/* ── Step 7: Done ── */}
        {step === 7 && (
          <div className="space-y-6 rounded-xl border bg-white p-8 shadow-sm text-center">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
              <PartyPopper className="h-8 w-8 text-green-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">{t("step3Title")}</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {company.company_name} is ready. You can explore features or check your setup health in Settings.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3 text-left">
              {[
                { label: "Create Invoice", href: "/invoices/new", done: false },
                { label: "Add Inventory",  href: "/inventory",    done: productSaved },
                { label: "Import Data",    href: "/settings/data-import", done: false },
                { label: "Setup Health",   href: "/settings/setup-health", done: false },
              ].map(({ label, href, done }) => (
                <a
                  key={href}
                  href={href}
                  className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-gray-50 transition-colors"
                >
                  {done
                    ? <Check className="h-4 w-4 text-green-500 flex-shrink-0" />
                    : <div className="h-4 w-4 rounded-full border-2 border-gray-300 flex-shrink-0" />}
                  <span className="text-gray-700">{label}</span>
                </a>
              ))}
            </div>

            <Button
              disabled={loading}
              className="w-full bg-[#1a2332] hover:bg-[#2a3342] text-white"
              onClick={finishWizard}
            >
              {loading ? "…" : t("finish")}
            </Button>
          </div>
        )}

      </div>
    </div>
  );
}

// ── Field helper ─────────────────────────────────────────────────────────────

function Field({
  id, label, required, placeholder, hint, value, error, onChange,
}: {
  id: string; label: string; required?: boolean; placeholder?: string;
  hint?: string; value: string; error?: string; onChange: (v: string) => void;
}) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="text-sm font-medium text-gray-700">
        {label}{required && <span className="ml-1 text-red-500">*</span>}
      </label>
      <input
        id={id} type="text" placeholder={placeholder} value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`block w-full rounded-md border px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-1 ${
          error
            ? "border-red-400 focus:border-red-500 focus:ring-red-500"
            : "border-gray-300 focus:border-[#1a2332] focus:ring-[#1a2332]"
        }`}
      />
      {hint && !error && <p className="text-xs text-muted-foreground">{hint}</p>}
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}
