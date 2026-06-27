"use client";

import { useEffect, useState } from "react";
import { Loader2, ChevronLeft, Eye, EyeOff, Plus, Trash2 } from "lucide-react";
import { useRouter, useParams } from "next/navigation";
import { useLocale } from "next-intl";
import { toast } from "sonner";
import { api } from "@/lib/api-client";

type Tab = "profile" | "contracts" | "emergency" | "documents";

interface Profile {
  full_legal_name: string | null;
  date_of_birth: string | null;
  department: string | null;
  status: string;
  job_title: string | null;
  employment_type: string;
  start_date: string | null;
  end_date: string | null;
  bank_name: string | null;
  bank_account: string | null;
  national_id: string | null;
  address: string | null;
  reports_to_staff_id: string | null;
}

interface Contract {
  id: string;
  contract_type: string;
  title: string | null;
  start_date: string;
  end_date: string | null;
  salary: string | null;
  currency: string;
  hours_per_week: string | null;
  file_url: string | null;
  probation_end_date: string | null;
  notice_period_days: number | null;
}

interface EmergencyContact {
  id: string;
  name: string;
  relationship: string | null;
  phone: string | null;
  email: string | null;
}

interface Document {
  id: string;
  file_name: string;
  file_url: string;
  created_at: string;
}

const STATUS_STYLE: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  on_leave: "bg-amber-100 text-amber-700",
  terminated: "bg-rose-100 text-rose-700",
};

const STATUS_LABEL: Record<string, string> = {
  active: "Active",
  on_leave: "On Leave",
  terminated: "Terminated",
};

const DEPARTMENTS = [
  "Engineering", "Sales", "Finance", "HR", "Operations",
  "Marketing", "Customer Success", "Management",
];

export default function EmployeePage() {
  const params = useParams();
  const staffId = params.id as string;
  const router = useRouter();
  const locale = useLocale();
  const [tab, setTab] = useState<Tab>("profile");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [contacts, setContacts] = useState<EmergencyContact[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showBankAccount, setShowBankAccount] = useState(false);
  const [showNationalId, setShowNationalId] = useState(false);
  const [form, setForm] = useState<Partial<Profile>>({});
  const [contractForm, setContractForm] = useState({
    contract_type: "permanent", title: "", start_date: "", end_date: "",
    salary: "", currency: "SEK", probation_end_date: "", notice_period_days: "",
  });
  const [showContractForm, setShowContractForm] = useState(false);
  const [contactForm, setContactForm] = useState({ name: "", relationship: "", phone: "", email: "" });
  const [showContactForm, setShowContactForm] = useState(false);

  useEffect(() => {
    setLoading(true);
    const reqs: Promise<unknown>[] = [
      api.get(`/api/hr/employees/${staffId}/profile`).then(setProfile).catch(() => {}),
      api.get(`/api/hr/employees/${staffId}/contracts`).then(setContracts).catch(() => {}),
      api.get(`/api/hr/employees/${staffId}/emergency-contacts`).then(setContacts).catch(() => {}),
      api.get(`/api/documents/linked/staff/${staffId}`).then(setDocuments).catch(() => {}),
    ];
    Promise.all(reqs).finally(() => setLoading(false));
  }, [staffId]);

  useEffect(() => {
    if (profile) setForm({ ...profile });
  }, [profile]);

  async function saveProfile() {
    setSaving(true);
    try {
      const updated = await api.post(`/api/hr/employees/${staffId}/profile`, form);
      setProfile(updated);
      toast.success("Profile saved");
    } catch {
      toast.error("Failed to save profile");
    } finally {
      setSaving(false);
    }
  }

  async function setStatus(newStatus: string) {
    setSaving(true);
    try {
      const updated = await api.post(`/api/hr/employees/${staffId}/profile`, { ...form, status: newStatus });
      setProfile(updated);
      setForm((f) => ({ ...f, status: newStatus }));
      toast.success(`Status set to ${STATUS_LABEL[newStatus] ?? newStatus}`);
    } catch {
      toast.error("Failed to update status");
    } finally {
      setSaving(false);
    }
  }

  async function createContract() {
    try {
      const payload = {
        ...contractForm,
        salary: contractForm.salary ? parseFloat(contractForm.salary) : null,
        notice_period_days: contractForm.notice_period_days ? parseInt(contractForm.notice_period_days) : null,
        end_date: contractForm.end_date || null,
        probation_end_date: contractForm.probation_end_date || null,
      };
      const created = await api.post(`/api/hr/employees/${staffId}/contracts`, payload);
      setContracts((c) => [...c, created]);
      setShowContractForm(false);
      setContractForm({ contract_type: "permanent", title: "", start_date: "", end_date: "", salary: "", currency: "SEK", probation_end_date: "", notice_period_days: "" });
      toast.success("Contract created");
    } catch {
      toast.error("Failed to create contract");
    }
  }

  async function deleteContract(id: string) {
    try {
      await api.delete(`/api/hr/employees/${staffId}/contracts/${id}`);
      setContracts((c) => c.filter((x) => x.id !== id));
      toast.success("Contract deleted");
    } catch {
      toast.error("Failed to delete contract");
    }
  }

  async function createContact() {
    try {
      const created = await api.post(`/api/hr/employees/${staffId}/emergency-contacts`, contactForm);
      setContacts((c) => [...c, created]);
      setShowContactForm(false);
      setContactForm({ name: "", relationship: "", phone: "", email: "" });
      toast.success("Contact added");
    } catch {
      toast.error("Failed to add contact");
    }
  }

  async function deleteContact(id: string) {
    try {
      await api.delete(`/api/hr/employees/${staffId}/emergency-contacts/${id}`);
      setContacts((c) => c.filter((x) => x.id !== id));
      toast.success("Contact removed");
    } catch {
      toast.error("Failed to remove contact");
    }
  }

  const TABS: { key: Tab; label: string }[] = [
    { key: "profile", label: "Profile" },
    { key: "contracts", label: "Contracts" },
    { key: "emergency", label: "Emergency" },
    { key: "documents", label: "Documents" },
  ];

  const currentStatus = form.status ?? "active";

  if (loading) {
    return (
      <div className="flex items-center justify-center h-60">
        <Loader2 className="w-6 h-6 animate-spin text-vf-accent" />
      </div>
    );
  }

  return (
    <div className="vf-section max-w-3xl">
      <button onClick={() => router.push(`/${locale}/hr`)} className="flex items-center gap-1 text-sm text-muted-foreground mb-4 hover:text-foreground">
        <ChevronLeft className="w-4 h-4" /> Back to Employees
      </button>

      {/* Status banner */}
      <div className="flex items-center gap-3 mb-5">
        <span className={`px-2.5 py-1 rounded-full text-sm font-medium ${STATUS_STYLE[currentStatus] ?? "bg-gray-100 text-gray-600"}`}>
          {STATUS_LABEL[currentStatus] ?? currentStatus}
        </span>
        {currentStatus !== "active" && (
          <button onClick={() => setStatus("active")} className="vf-btn-ghost text-xs">Reactivate</button>
        )}
        {currentStatus !== "on_leave" && (
          <button onClick={() => setStatus("on_leave")} className="vf-btn-ghost text-xs">Set On Leave</button>
        )}
        {currentStatus !== "terminated" && (
          <button onClick={() => setStatus("terminated")} className="text-xs px-2 py-1 rounded border border-rose-300 text-rose-600 hover:bg-rose-50 transition-colors">Terminate</button>
        )}
      </div>

      <div className="flex gap-2 border-b mb-6">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === t.key ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Profile Tab */}
      {tab === "profile" && (
        <div className="space-y-4 max-w-lg">
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="text-xs font-medium text-muted-foreground">Full Legal Name</label>
              <input className="vf-input w-full mt-1" placeholder="As on legal ID" value={form.full_legal_name ?? ""} onChange={(e) => setForm((f) => ({ ...f, full_legal_name: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Date of Birth</label>
              <input type="date" className="vf-input w-full mt-1" value={form.date_of_birth ?? ""} onChange={(e) => setForm((f) => ({ ...f, date_of_birth: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Department</label>
              <select className="vf-input w-full mt-1" value={form.department ?? ""} onChange={(e) => setForm((f) => ({ ...f, department: e.target.value }))}>
                <option value="">— select —</option>
                {DEPARTMENTS.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Job Title</label>
              <input className="vf-input w-full mt-1" value={form.job_title ?? ""} onChange={(e) => setForm((f) => ({ ...f, job_title: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Employment Type</label>
              <select className="vf-input w-full mt-1" value={form.employment_type ?? "full_time"} onChange={(e) => setForm((f) => ({ ...f, employment_type: e.target.value }))}>
                <option value="full_time">Full-time</option>
                <option value="part_time">Part-time</option>
                <option value="contractor">Contractor</option>
                <option value="intern">Intern</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Start Date</label>
              <input type="date" className="vf-input w-full mt-1" value={form.start_date ?? ""} onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">End Date</label>
              <input type="date" className="vf-input w-full mt-1" value={form.end_date ?? ""} onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))} />
            </div>
          </div>

          <hr className="border-border" />

          <div>
            <label className="text-xs font-medium text-muted-foreground">Bank Name</label>
            <input className="vf-input w-full mt-1" value={form.bank_name ?? ""} onChange={(e) => setForm((f) => ({ ...f, bank_name: e.target.value }))} />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Bank Account (PII)</label>
            <div className="flex gap-2 mt-1">
              <input type={showBankAccount ? "text" : "password"} className="vf-input flex-1" value={form.bank_account ?? ""} onChange={(e) => setForm((f) => ({ ...f, bank_account: e.target.value }))} />
              <button onClick={() => setShowBankAccount((x) => !x)} className="vf-btn-ghost px-2">
                {showBankAccount ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">National ID (PII)</label>
            <div className="flex gap-2 mt-1">
              <input type={showNationalId ? "text" : "password"} className="vf-input flex-1" value={form.national_id ?? ""} onChange={(e) => setForm((f) => ({ ...f, national_id: e.target.value }))} />
              <button onClick={() => setShowNationalId((x) => !x)} className="vf-btn-ghost px-2">
                {showNationalId ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Address</label>
            <textarea className="vf-input w-full mt-1 h-20 resize-none" value={form.address ?? ""} onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))} />
          </div>
          <button onClick={saveProfile} disabled={saving} className="vf-btn flex items-center gap-2">
            {saving && <Loader2 className="w-3 h-3 animate-spin" />} Save Profile
          </button>
        </div>
      )}

      {/* Contracts Tab */}
      {tab === "contracts" && (
        <div>
          <button onClick={() => setShowContractForm((x) => !x)} className="vf-btn-ghost flex items-center gap-1.5 text-sm mb-4">
            <Plus className="w-4 h-4" /> Add Contract
          </button>
          {showContractForm && (
            <div className="border rounded-lg p-4 mb-4 grid grid-cols-2 gap-3 max-w-lg bg-muted/30">
              <div>
                <label className="text-xs font-medium text-muted-foreground">Type</label>
                <select className="vf-input w-full mt-1" value={contractForm.contract_type} onChange={(e) => setContractForm((f) => ({ ...f, contract_type: e.target.value }))}>
                  <option value="permanent">Permanent</option>
                  <option value="fixed_term">Fixed-term</option>
                  <option value="freelance">Freelance</option>
                  <option value="probation">Probation</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Title</label>
                <input className="vf-input w-full mt-1" value={contractForm.title} onChange={(e) => setContractForm((f) => ({ ...f, title: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Start Date</label>
                <input type="date" className="vf-input w-full mt-1" value={contractForm.start_date} onChange={(e) => setContractForm((f) => ({ ...f, start_date: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">End Date</label>
                <input type="date" className="vf-input w-full mt-1" value={contractForm.end_date} onChange={(e) => setContractForm((f) => ({ ...f, end_date: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Salary</label>
                <input type="number" className="vf-input w-full mt-1" value={contractForm.salary} onChange={(e) => setContractForm((f) => ({ ...f, salary: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Currency</label>
                <input className="vf-input w-full mt-1" value={contractForm.currency} onChange={(e) => setContractForm((f) => ({ ...f, currency: e.target.value }))} maxLength={3} />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Probation End Date</label>
                <input type="date" className="vf-input w-full mt-1" value={contractForm.probation_end_date} onChange={(e) => setContractForm((f) => ({ ...f, probation_end_date: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Notice Period (days)</label>
                <input type="number" className="vf-input w-full mt-1" value={contractForm.notice_period_days} onChange={(e) => setContractForm((f) => ({ ...f, notice_period_days: e.target.value }))} />
              </div>
              <div className="col-span-2 flex gap-2">
                <button onClick={createContract} className="vf-btn">Create</button>
                <button onClick={() => setShowContractForm(false)} className="vf-btn-ghost">Cancel</button>
              </div>
            </div>
          )}
          {contracts.length === 0 ? (
            <p className="vf-text-m text-muted-foreground">No contracts yet.</p>
          ) : (
            <div className="space-y-2">
              {contracts.map((c) => (
                <div key={c.id} className="border rounded-lg p-3 flex items-start justify-between">
                  <div>
                    <p className="text-sm font-medium">{c.title || c.contract_type}</p>
                    <p className="text-xs text-muted-foreground">
                      {c.start_date} → {c.end_date ?? "open"}{c.salary ? ` · ${c.salary} ${c.currency}` : ""}
                    </p>
                    {(c.probation_end_date || c.notice_period_days) && (
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {c.probation_end_date && `Probation until ${c.probation_end_date}`}
                        {c.probation_end_date && c.notice_period_days && " · "}
                        {c.notice_period_days && `${c.notice_period_days}d notice`}
                      </p>
                    )}
                  </div>
                  <button onClick={() => deleteContract(c.id)} className="text-destructive hover:opacity-70 mt-0.5">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Emergency Tab */}
      {tab === "emergency" && (
        <div>
          <button onClick={() => setShowContactForm((x) => !x)} className="vf-btn-ghost flex items-center gap-1.5 text-sm mb-4">
            <Plus className="w-4 h-4" /> Add Contact
          </button>
          {showContactForm && (
            <div className="border rounded-lg p-4 mb-4 grid grid-cols-2 gap-3 max-w-lg bg-muted/30">
              <div>
                <label className="text-xs font-medium text-muted-foreground">Name</label>
                <input className="vf-input w-full mt-1" value={contactForm.name} onChange={(e) => setContactForm((f) => ({ ...f, name: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Relationship</label>
                <input className="vf-input w-full mt-1" value={contactForm.relationship} onChange={(e) => setContactForm((f) => ({ ...f, relationship: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Phone</label>
                <input className="vf-input w-full mt-1" value={contactForm.phone} onChange={(e) => setContactForm((f) => ({ ...f, phone: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Email</label>
                <input className="vf-input w-full mt-1" value={contactForm.email} onChange={(e) => setContactForm((f) => ({ ...f, email: e.target.value }))} />
              </div>
              <div className="col-span-2 flex gap-2">
                <button onClick={createContact} className="vf-btn">Add</button>
                <button onClick={() => setShowContactForm(false)} className="vf-btn-ghost">Cancel</button>
              </div>
            </div>
          )}
          {contacts.length === 0 ? (
            <p className="vf-text-m text-muted-foreground">No emergency contacts.</p>
          ) : (
            <div className="space-y-2">
              {contacts.map((c) => (
                <div key={c.id} className="border rounded-lg p-3 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">{c.name}</p>
                    <p className="text-xs text-muted-foreground">{[c.relationship, c.phone, c.email].filter(Boolean).join(" · ")}</p>
                  </div>
                  <button onClick={() => deleteContact(c.id)} className="text-destructive hover:opacity-70">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Documents Tab */}
      {tab === "documents" && (
        <div>
          {documents.length === 0 ? (
            <p className="vf-text-m text-muted-foreground">No documents uploaded.</p>
          ) : (
            <div className="space-y-2">
              {documents.map((d) => (
                <a key={d.id} href={d.file_url} target="_blank" rel="noreferrer" className="border rounded-lg p-3 flex items-center justify-between hover:bg-accent transition-colors">
                  <p className="text-sm">{d.file_name}</p>
                  <p className="text-xs text-muted-foreground">{new Date(d.created_at).toLocaleDateString()}</p>
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
