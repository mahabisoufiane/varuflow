"use client";
import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api-client";
import pageStyles from "./page.module.scss";

type CredentialType = "certification" | "training" | "award" | "experience";

interface Credential {
  id: string;
  staff_id: string;
  credential_type: CredentialType;
  title: string;
  issuing_body: string | null;
  issued_date: string | null;
  expiry_date: string | null;
  is_visible_to_customers: boolean;
}

const TYPE_BADGE: Record<CredentialType, string> = {
  certification: "bg-blue-100 text-blue-800",
  training: "bg-green-100 text-green-800",
  award: "bg-yellow-100 text-yellow-800",
  experience: "bg-gray-100 text-gray-700",
};

const TYPE_MODULE: Record<CredentialType, keyof typeof pageStyles> = {
  certification: "typeCertification",
  training:      "typeTraining",
  award:         "typeAward",
  experience:    "typeExperience",
};

export default function CredentialsPage() {
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [staffFilter, setStaffFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [addOpen, setAddOpen] = useState(false);
  const [addForm, setAddForm] = useState({
    staff_id: "",
    credential_type: "certification" as CredentialType,
    title: "",
    issuing_body: "",
    issued_date: "",
    expiry_date: "",
    is_visible_to_customers: false,
  });
  const [addError, setAddError] = useState("");
  const [addLoading, setAddLoading] = useState(false);

  async function loadCredentials() {
    setLoading(true);
    setError("");
    try {
      const qs = staffFilter ? `?staff_id=${encodeURIComponent(staffFilter)}` : "";
      const data = await api.get<Credential[] | { items?: Credential[] }>(`/api/staff-credentials${qs}`);
      setCredentials(Array.isArray(data) ? data : data.items ?? []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load credentials");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCredentials();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleAdd() {
    setAddLoading(true);
    setAddError("");
    try {
      const body: Record<string, unknown> = {
        staff_id: addForm.staff_id,
        credential_type: addForm.credential_type,
        title: addForm.title,
        is_visible_to_customers: addForm.is_visible_to_customers,
      };
      if (addForm.issuing_body) body.issuing_body = addForm.issuing_body;
      if (addForm.issued_date) body.issued_date = addForm.issued_date;
      if (addForm.expiry_date) body.expiry_date = addForm.expiry_date;

      await api.post<Credential>("/api/staff-credentials", body);
      setAddOpen(false);
      setAddForm({
        staff_id: "",
        credential_type: "certification",
        title: "",
        issuing_body: "",
        issued_date: "",
        expiry_date: "",
        is_visible_to_customers: false,
      });
      loadCredentials();
    } catch (e: unknown) {
      setAddError(e instanceof Error ? e.message : "Failed to add credential");
    } finally {
      setAddLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Staff Credentials</h1>
        <Button onClick={() => setAddOpen(!addOpen)}>Add Credential</Button>
      </div>

      {/* Filter */}
      <Card>
        <CardContent className="pt-4 flex gap-3 items-end">
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Staff ID</label>
            <Input
              value={staffFilter}
              onChange={(e) => setStaffFilter(e.target.value)}
              placeholder="UUID"
              className="w-64"
            />
          </div>
          <Button variant="outline" onClick={loadCredentials}>Search</Button>
        </CardContent>
      </Card>

      {/* Add form */}
      {addOpen && (
        <Card>
          <CardHeader><CardTitle>Add Credential</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <Input
              placeholder="Staff ID (UUID) *"
              value={addForm.staff_id}
              onChange={(e) => setAddForm((f) => ({ ...f, staff_id: e.target.value }))}
            />
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Type *</label>
              <select
                value={addForm.credential_type}
                onChange={(e) =>
                  setAddForm((f) => ({ ...f, credential_type: e.target.value as CredentialType }))
                }
                className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm w-full"
              >
                <option value="certification">Certification</option>
                <option value="training">Training</option>
                <option value="award">Award</option>
                <option value="experience">Experience</option>
              </select>
            </div>
            <Input
              placeholder="Title *"
              value={addForm.title}
              onChange={(e) => setAddForm((f) => ({ ...f, title: e.target.value }))}
            />
            <Input
              placeholder="Issuing Body"
              value={addForm.issuing_body}
              onChange={(e) => setAddForm((f) => ({ ...f, issuing_body: e.target.value }))}
            />
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Issued Date</label>
                <Input
                  type="date"
                  value={addForm.issued_date}
                  onChange={(e) => setAddForm((f) => ({ ...f, issued_date: e.target.value }))}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Expiry Date</label>
                <Input
                  type="date"
                  value={addForm.expiry_date}
                  onChange={(e) => setAddForm((f) => ({ ...f, expiry_date: e.target.value }))}
                />
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={addForm.is_visible_to_customers}
                onChange={(e) =>
                  setAddForm((f) => ({ ...f, is_visible_to_customers: e.target.checked }))
                }
              />
              Visible to Customers
            </label>
            {addError && <p className="text-red-500 text-sm">{addError}</p>}
            <div className="flex gap-2">
              <Button onClick={handleAdd} disabled={addLoading}>
                {addLoading ? "Saving…" : "Save"}
              </Button>
              <Button variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {error && <p className="text-red-500 text-sm">{error}</p>}
      {loading && <p className="text-muted-foreground">Loading...</p>}

      {!loading && (
        <Card>
          <CardContent className="pt-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Staff ID</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Issuing Body</TableHead>
                  <TableHead>Issued</TableHead>
                  <TableHead>Expiry</TableHead>
                  <TableHead>Visible</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {credentials.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                      No credentials found
                    </TableCell>
                  </TableRow>
                )}
                {credentials.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-mono text-xs">
                      {c.staff_id.slice(0, 8)}…
                    </TableCell>
                    <TableCell>
                      <span
                        className={pageStyles[TYPE_MODULE[c.credential_type] ?? "typeExperience"]}
                      >
                        {c.credential_type}
                      </span>
                    </TableCell>
                    <TableCell>{c.title}</TableCell>
                    <TableCell>{c.issuing_body ?? "—"}</TableCell>
                    <TableCell>{c.issued_date ?? "—"}</TableCell>
                    <TableCell>{c.expiry_date ?? "—"}</TableCell>
                    <TableCell>
                      <Badge variant={c.is_visible_to_customers ? "default" : "secondary"}>
                        {c.is_visible_to_customers ? "Yes" : "No"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
