"use client"

import { useState, useEffect } from "react"
import { useTranslations } from "next-intl"
import { api } from "@/lib/api-client"
import { AlertTriangle, Send, Clock, ChevronRight } from "lucide-react"
import { toast } from "sonner"

interface DunningItem {
  id: string
  invoice_id: string
  invoice_number: string
  customer_name: string
  customer_email: string
  amount_due: number
  currency: string
  due_date: string
  days_overdue: number
  stage: number
  last_reminder_sent: string | null
  status: string
}

const stageConfig: Record<number, { label: string; color: string }> = {
  1: { label: "1 day", color: "bg-yellow-100 text-yellow-800" },
  2: { label: "7 days", color: "bg-orange-100 text-orange-800" },
  3: { label: "14 days", color: "bg-red-100 text-red-800" },
  4: { label: "30+ days", color: "bg-red-200 text-red-900" },
}

function getStage(daysOverdue: number): number {
  if (daysOverdue >= 30) return 4
  if (daysOverdue >= 14) return 3
  if (daysOverdue >= 7) return 2
  return 1
}

export default function DunningPage() {
  const t = useTranslations()
  const [items, setItems] = useState<DunningItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchDunning()
  }, [])

  async function fetchDunning() {
    try {
      setLoading(true)
      const data = await api.get("/api/invoices/dunning")
      setItems(data)
    } catch (error) {
      toast.error("Failed to load dunning data. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  async function sendReminder(itemId: string) {
    try {
      await api.post(`/api/invoices/dunning/${itemId}/remind`, {})
      toast.success("Reminder sent successfully.")
      fetchDunning()
    } catch (error) {
      toast.error("Failed to send reminder.")
    }
  }

  const stageCounts = items.reduce<Record<number, number>>((acc, item) => {
    const s = item.stage ?? getStage(item.days_overdue)
    acc[s] = (acc[s] || 0) + 1
    return acc
  }, {})

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold vf-text-1">Dunning Management</h1>
        <p className="vf-text-m mt-1">Track and manage overdue invoice reminders</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((stage) => {
          const cfg = stageConfig[stage]
          return (
            <div key={stage} className="vf-bg-card vf-border rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cfg.color}`}>
                  {cfg.label}
                </span>
                <Clock className="w-4 h-4 vf-text-m" />
              </div>
              <p className="text-2xl font-semibold vf-text-1">{stageCounts[stage] || 0}</p>
              <p className="text-sm vf-text-m">invoices</p>
            </div>
          )
        })}
      </div>

      {loading ? (
        <div className="vf-bg-card vf-border rounded-lg p-8 text-center vf-text-m">
          Loading...
        </div>
      ) : items.length === 0 ? (
        <div className="vf-bg-card vf-border rounded-lg p-12 text-center">
          <AlertTriangle className="w-12 h-12 mx-auto mb-4 vf-text-m" />
          <p className="vf-text-1 font-medium">No overdue invoices</p>
          <p className="vf-text-m mt-1">All invoices are paid on time.</p>
        </div>
      ) : (
        <div className="vf-bg-card vf-border rounded-lg overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b vf-border">
                <th className="text-left px-4 py-3 vf-text-m text-sm font-medium">Invoice</th>
                <th className="text-left px-4 py-3 vf-text-m text-sm font-medium">Customer</th>
                <th className="text-right px-4 py-3 vf-text-m text-sm font-medium">Amount</th>
                <th className="text-left px-4 py-3 vf-text-m text-sm font-medium">Due Date</th>
                <th className="text-left px-4 py-3 vf-text-m text-sm font-medium">Overdue</th>
                <th className="text-left px-4 py-3 vf-text-m text-sm font-medium">Stage</th>
                <th className="text-left px-4 py-3 vf-text-m text-sm font-medium">Last Reminder</th>
                <th className="text-right px-4 py-3 vf-text-m text-sm font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const stage = item.stage ?? getStage(item.days_overdue)
                const cfg = stageConfig[stage]
                return (
                  <tr key={item.id} className="border-b vf-border last:border-b-0 hover:bg-black/5 transition-colors">
                    <td className="px-4 py-3 vf-text-1 font-medium">{item.invoice_number}</td>
                    <td className="px-4 py-3 vf-text-1">{item.customer_name}</td>
                    <td className="px-4 py-3 vf-text-1 text-right font-medium">{item.amount_due.toLocaleString()} {item.currency}</td>
                    <td className="px-4 py-3 vf-text-m">{new Date(item.due_date).toLocaleDateString()}</td>
                    <td className="px-4 py-3 vf-text-1">{item.days_overdue} days</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cfg.color}`}>
                        {cfg.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 vf-text-m">
                      {item.last_reminder_sent ? new Date(item.last_reminder_sent).toLocaleDateString() : "Never"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => sendReminder(item.id)}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-sm bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                      >
                        <Send className="w-3 h-3" />
                        Remind
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
