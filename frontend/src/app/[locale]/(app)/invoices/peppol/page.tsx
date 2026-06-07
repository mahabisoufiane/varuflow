"use client"

import { useState, useEffect } from "react"
import { useTranslations } from "next-intl"
import { api } from "@/lib/api-client"
import { Globe, CheckCircle, XCircle, Settings, RefreshCw } from "lucide-react"
import { toast } from "sonner"
import styles from "./page.module.scss"

interface PeppolStatus {
  registered: boolean
  participant_id: string | null
  scheme_id: string | null
  registration_status: "active" | "pending" | "inactive" | "error"
  last_synced: string | null
  supported_document_types: string[]
}

const registrationLabels: Record<string, { label: string; className: string }> = {
  active: { label: "Active", className: "bg-green-100 text-green-800" },
  pending: { label: "Pending", className: "bg-yellow-100 text-yellow-800" },
  inactive: { label: "Inactive", className: "bg-gray-100 text-gray-800" },
  error: { label: "Error", className: "bg-red-100 text-red-800" },
}

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  active:   "statusActive",
  pending:  "statusPending",
  inactive: "statusInactive",
  error:    "statusError",
}

export default function PeppolPage() {
  const t = useTranslations()
  const [status, setStatus] = useState<PeppolStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [participantId, setParticipantId] = useState("")
  const [schemeId, setSchemeId] = useState("0007")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetchStatus()
  }, [])

  async function fetchStatus() {
    try {
      setLoading(true)
      const data = await api.get("/api/integrations/peppol/status")
      setStatus(data)
      if (data.participant_id) setParticipantId(data.participant_id)
      if (data.scheme_id) setSchemeId(data.scheme_id)
    } catch (error) {
      toast.error("Failed to load Peppol status. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  async function saveSettings() {
    if (!participantId.trim()) {
      toast.error("Participant ID is required.")
      return
    }
    try {
      setSaving(true)
      await api.post("/api/integrations/peppol/configure", {
        participant_id: participantId.trim(),
        scheme_id: schemeId,
      })
      toast.success("Peppol settings saved.")
      fetchStatus()
    } catch (error) {
      toast.error("Failed to save Peppol settings.")
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="p-6">
        <div className="vf-bg-card vf-border rounded-lg p-8 text-center vf-text-m">Loading...</div>
      </div>
    )
  }

  const regCfg = status ? registrationLabels[status.registration_status] || registrationLabels.inactive : registrationLabels.inactive

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold vf-text-1">Peppol E-Invoicing</h1>
        <p className="vf-text-m mt-1">Configure Peppol network settings for electronic invoicing</p>
      </div>

      <div className="vf-bg-card vf-border rounded-lg p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Globe className="w-6 h-6 vf-text-1" />
            <div>
              <p className="vf-text-1 font-medium">Registration Status</p>
              <p className="vf-text-m text-sm">Your Peppol network registration</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className={styles[STATUS_MODULE[status?.registration_status ?? "inactive"] ?? "statusInactive"]}>
              {status?.registered ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
              {regCfg.label}
            </span>
            <button onClick={fetchStatus} className="p-1.5 rounded-md hover:bg-black/5 transition-colors">
              <RefreshCw className="w-4 h-4 vf-text-m" />
            </button>
          </div>
        </div>
        {status?.last_synced && (
          <p className="vf-text-m text-sm">Last synced: {new Date(status.last_synced).toLocaleString()}</p>
        )}
      </div>

      <div className="vf-bg-card vf-border rounded-lg p-5 space-y-4">
        <div className="flex items-center gap-2 mb-2">
          <Settings className="w-5 h-5 vf-text-1" />
          <h2 className="vf-text-1 font-medium">Participant Configuration</h2>
        </div>

        <div>
          <label className="block text-sm font-medium vf-text-1 mb-1">Scheme ID</label>
          <select
            value={schemeId}
            onChange={(e) => setSchemeId(e.target.value)}
            className="w-full px-3 py-2 rounded-lg vf-border vf-bg-card vf-text-1 text-sm"
          >
            <option value="0007">0007 - Swedish Organization Number</option>
            <option value="0192">0192 - Norwegian Organization Number</option>
            <option value="0184">0184 - Danish CVR Number</option>
            <option value="0088">0088 - EAN Location Code</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium vf-text-1 mb-1">Participant ID</label>
          <input
            type="text"
            value={participantId}
            onChange={(e) => setParticipantId(e.target.value)}
            placeholder="e.g. 5567891234"
            className="w-full px-3 py-2 rounded-lg vf-border vf-bg-card vf-text-1 text-sm"
          />
          <p className="vf-text-m text-xs mt-1">Your organization number on the Peppol network</p>
        </div>

        <button
          onClick={saveSettings}
          disabled={saving}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save Settings"}
        </button>
      </div>

      {status?.supported_document_types && status.supported_document_types.length > 0 && (
        <div className="vf-bg-card vf-border rounded-lg p-5">
          <h2 className="vf-text-1 font-medium mb-3">Supported Document Types</h2>
          <div className="flex flex-wrap gap-2">
            {status.supported_document_types.map((type) => (
              <span key={type} className="px-2.5 py-1 rounded-md bg-gray-100 text-gray-800 text-xs font-medium">
                {type}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
