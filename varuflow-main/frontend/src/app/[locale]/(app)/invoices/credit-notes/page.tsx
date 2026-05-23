"use client"

import { useState, useEffect } from "react"
import { useTranslations } from "next-intl"
import { api } from "@/lib/api-client"
import { FileText, Plus, ArrowLeft } from "lucide-react"
import { toast } from "sonner"

interface CreditNote {
  id: string
  credit_note_number: string
  original_invoice_id: string
  original_invoice_number: string
  customer_name: string
  amount: number
  currency: string
  reason: string
  created_at: string
  status: string
}

export default function CreditNotesPage() {
  const t = useTranslations()
  const [creditNotes, setCreditNotes] = useState<CreditNote[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchCreditNotes()
  }, [])

  async function fetchCreditNotes() {
    try {
      setLoading(true)
      const data = await api.get("/api/invoices/credit-notes")
      setCreditNotes(data)
    } catch (error) {
      toast.error("Failed to load credit notes. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold vf-text-1">Credit Notes</h1>
          <p className="vf-text-m mt-1">Manage credit notes linked to invoices</p>
        </div>
        <button className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors">
          <Plus className="w-4 h-4" />
          New Credit Note
        </button>
      </div>

      {loading ? (
        <div className="vf-bg-card vf-border rounded-lg p-8 text-center vf-text-m">
          Loading...
        </div>
      ) : creditNotes.length === 0 ? (
        <div className="vf-bg-card vf-border rounded-lg p-12 text-center">
          <FileText className="w-12 h-12 mx-auto mb-4 vf-text-m" />
          <p className="vf-text-1 font-medium">No credit notes yet</p>
          <p className="vf-text-m mt-1">Credit notes will appear here once created.</p>
        </div>
      ) : (
        <div className="vf-bg-card vf-border rounded-lg overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b vf-border">
                <th className="text-left px-4 py-3 vf-text-m text-sm font-medium">Number</th>
                <th className="text-left px-4 py-3 vf-text-m text-sm font-medium">Original Invoice</th>
                <th className="text-left px-4 py-3 vf-text-m text-sm font-medium">Customer</th>
                <th className="text-left px-4 py-3 vf-text-m text-sm font-medium">Reason</th>
                <th className="text-right px-4 py-3 vf-text-m text-sm font-medium">Amount</th>
                <th className="text-left px-4 py-3 vf-text-m text-sm font-medium">Status</th>
                <th className="text-left px-4 py-3 vf-text-m text-sm font-medium">Date</th>
              </tr>
            </thead>
            <tbody>
              {creditNotes.map((cn) => (
                <tr key={cn.id} className="border-b vf-border last:border-b-0 hover:bg-black/5 transition-colors">
                  <td className="px-4 py-3 vf-text-1 font-medium">{cn.credit_note_number}</td>
                  <td className="px-4 py-3 vf-text-m flex items-center gap-1">
                    <ArrowLeft className="w-3 h-3" />
                    {cn.original_invoice_number}
                  </td>
                  <td className="px-4 py-3 vf-text-1">{cn.customer_name}</td>
                  <td className="px-4 py-3 vf-text-m">{cn.reason}</td>
                  <td className="px-4 py-3 vf-text-1 text-right font-medium">
                    {cn.amount.toLocaleString()} {cn.currency}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                      cn.status === "issued" ? "bg-green-100 text-green-800" :
                      cn.status === "draft" ? "bg-gray-100 text-gray-800" :
                      "bg-yellow-100 text-yellow-800"
                    }`}>
                      {cn.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 vf-text-m">{new Date(cn.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
