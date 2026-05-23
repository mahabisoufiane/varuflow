"use client";

import { useCallback, useEffect, useState } from "react";
import { Store, Loader2, Save, ToggleLeft, ToggleRight } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";

interface Storefront {
  id: string;
  slug: string;
  name: string;
  tagline: string | null;
  logo_url: string | null;
  primary_color: string | null;
  is_active: boolean;
  payment_methods: string[];
  currency: string;
}

const PAYMENT_OPTIONS = [
  { value: "card", label: "Card" },
  { value: "klarna", label: "Klarna" },
  { value: "swish", label: "Swish" },
  { value: "vipps", label: "Vipps" },
];

const CURRENCIES = ["SEK", "NOK", "DKK", "EUR"];

export default function StorefrontConfigPage() {
  const [storefront, setStorefront] = useState<Storefront | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Form state
  const [name, setName] = useState("");
  const [tagline, setTagline] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [primaryColor, setPrimaryColor] = useState("#1a2332");
  const [paymentMethods, setPaymentMethods] = useState<string[]>(["card"]);
  const [currency, setCurrency] = useState("SEK");
  const [isActive, setIsActive] = useState(false);

  // Create mode
  const [createMode, setCreateMode] = useState(false);
  const [newSlug, setNewSlug] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get("/api/shop/config");
      setStorefront(data);
      setName(data.name ?? "");
      setTagline(data.tagline ?? "");
      setLogoUrl(data.logo_url ?? "");
      setPrimaryColor(data.primary_color ?? "#1a2332");
      setPaymentMethods(data.payment_methods ?? ["card"]);
      setCurrency(data.currency ?? "SEK");
      setIsActive(data.is_active ?? false);
    } catch (err: unknown) {
      if ((err as { status?: number })?.status === 404) {
        setCreateMode(true);
      } else {
        toast.error("Failed to load storefront config");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleCreate = async () => {
    if (!name) {
      toast.error("Shop name is required");
      return;
    }
    setSaving(true);
    try {
      const data = await api.post("/api/shop/config", {
        name,
        slug: newSlug || undefined,
        tagline: tagline || undefined,
        logo_url: logoUrl || undefined,
        primary_color: primaryColor,
        payment_methods: paymentMethods.join(","),
        currency,
      });
      setStorefront(data);
      setCreateMode(false);
      toast.success("Storefront created");
    } catch {
      toast.error("Failed to create storefront");
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const data = await api.patch("/api/shop/config", {
        name: name || undefined,
        tagline: tagline || undefined,
        logo_url: logoUrl || undefined,
        primary_color: primaryColor || undefined,
        payment_methods: paymentMethods.join(","),
        currency,
        is_active: isActive,
      });
      setStorefront(data);
      toast.success("Storefront saved");
    } catch {
      toast.error("Failed to save storefront");
    } finally {
      setSaving(false);
    }
  };

  const togglePaymentMethod = (m: string) => {
    setPaymentMethods((prev) =>
      prev.includes(m) ? (prev.length > 1 ? prev.filter((p) => p !== m) : prev) : [...prev, m]
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-2xl space-y-6">
      <div className="flex items-center gap-3">
        <Store className="h-6 w-6 text-gray-600" />
        <h1 className="text-2xl font-semibold">Storefront</h1>
      </div>

      {/* Shop URL notice */}
      {storefront && (
        <div className="border rounded-xl bg-blue-50 px-4 py-3 text-sm text-blue-700">
          Your shop URL:{" "}
          <span className="font-mono font-medium">
            /shop/{storefront.slug}
          </span>
          <span className="ml-2 text-xs text-blue-400">(slug cannot be changed after creation)</span>
        </div>
      )}

      <div className="border rounded-xl bg-white p-6 space-y-5">
        {/* Name */}
        <div>
          <label className="text-sm font-medium text-gray-700">Shop name *</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300"
            placeholder="My Shop"
          />
        </div>

        {/* Slug (only shown in create mode) */}
        {createMode && (
          <div>
            <label className="text-sm font-medium text-gray-700">Slug (optional)</label>
            <p className="text-xs text-gray-400 mb-1">Leave blank to auto-generate from shop name</p>
            <input
              type="text"
              value={newSlug}
              onChange={(e) => setNewSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"))}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300"
              placeholder="my-shop"
            />
          </div>
        )}

        {/* Tagline */}
        <div>
          <label className="text-sm font-medium text-gray-700">Tagline</label>
          <input
            type="text"
            value={tagline}
            onChange={(e) => setTagline(e.target.value)}
            className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300"
            placeholder="Quality goods for professionals"
          />
        </div>

        {/* Logo URL */}
        <div>
          <label className="text-sm font-medium text-gray-700">Logo URL</label>
          <input
            type="url"
            value={logoUrl}
            onChange={(e) => setLogoUrl(e.target.value)}
            className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300"
            placeholder="https://..."
          />
        </div>

        {/* Primary color */}
        <div>
          <label className="text-sm font-medium text-gray-700">Brand color</label>
          <div className="flex items-center gap-3 mt-1">
            <input
              type="color"
              value={primaryColor}
              onChange={(e) => setPrimaryColor(e.target.value)}
              className="h-10 w-16 rounded border cursor-pointer"
            />
            <span className="text-sm font-mono text-gray-500">{primaryColor}</span>
          </div>
        </div>

        {/* Payment methods */}
        <div>
          <label className="text-sm font-medium text-gray-700">Payment methods</label>
          <p className="text-xs text-gray-400 mb-2">Card is always required</p>
          <div className="flex gap-3 flex-wrap">
            {PAYMENT_OPTIONS.map((opt) => (
              <label key={opt.value} className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={paymentMethods.includes(opt.value)}
                  onChange={() => togglePaymentMethod(opt.value)}
                  disabled={opt.value === "card"}
                  className="rounded"
                />
                {opt.label}
              </label>
            ))}
          </div>
        </div>

        {/* Currency */}
        <div>
          <label className="text-sm font-medium text-gray-700">Currency</label>
          <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            className="mt-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300"
          >
            {CURRENCIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>

        {/* Active toggle (only in edit mode) */}
        {!createMode && (
          <div className="flex items-center justify-between pt-2 border-t">
            <div>
              <p className="text-sm font-medium text-gray-700">Store active</p>
              <p className="text-xs text-gray-400">
                {isActive ? "Your shop is publicly visible" : "Your shop is hidden from customers"}
              </p>
            </div>
            <button
              onClick={() => setIsActive((v) => !v)}
              className="flex items-center gap-2 text-sm"
            >
              {isActive ? (
                <ToggleRight className="h-8 w-8 text-green-600" />
              ) : (
                <ToggleLeft className="h-8 w-8 text-gray-400" />
              )}
            </button>
          </div>
        )}
      </div>

      <div className="flex justify-end">
        <button
          onClick={createMode ? handleCreate : handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-gray-700 disabled:opacity-50 transition-colors"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          {createMode ? "Create storefront" : "Save changes"}
        </button>
      </div>
    </div>
  );
}
