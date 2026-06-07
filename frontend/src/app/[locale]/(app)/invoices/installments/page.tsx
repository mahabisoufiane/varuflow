"use client"

import { useState, useEffect } from "react"
import { useTranslations } from "next-intl"
import { api } from "@/lib/api-client"
import { CalendarClock, Plus, CheckCircle, AlertCircle, Clock } from "lucide-react"
import { toast } from "sonner"
import styles from "./page.module.scss"

interface Installment {
  id: string
  invoice_id: string
  invoice_number: string
  customer_name: string
  total_amount: number
  paid_amount: number
  remaining_amount: number
  currency: string
  installment_count: number
  completed_count: number
  next_due_date: string | null
  status: "active" | "completed" | "overdue"
  created_at: string
}

const statusConfig = {
  active: { label: "Active", className: "bg-blue-100 text-blue-800", icon: Clock },
  completed: { label: "Completed", className: "bg-green-100 text-green-800", icon: CheckCircle },
  overdue: { label: "Overdue", className: "bg-red-100 text-red-800", icon: AlertCircle },
}

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  active:    "statusActive",
  completed: "statusCompleted",
  overdue:   "statusOverdue",
}

export default function InstallmentsPage() {
  const t = useTranslations()
  const [installments, setInstallments] = useState<Installment[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchInstallments()
  }, [])

  async function fetchInstallments() {
    try {
      setLoading(true)
      const data = await api.get("/api/invoices/installments")
      setInstallments(data)
    } catch (error) {
      toast.error("Failed to load installment plans. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold vf-text-1">Installment Plans</h1>
          <p className="vf-text-m mt-1">Track active installment plans and payment progress</p>
        </div>
        <button className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors">
          <Plus className="w-4 h-4" />
          New Plan
        </button>
      </div>

      {loading ? (
        <div className="vf-bg-card vf-border rounded-lg p-8 text-center vf-text-m">
          Loading...
        </div>
      ) : installments.length === 0 ? (
        <div className="vf-bg-card vf-border rounded-lg p-12 text-center">
          <CalendarClock className="w-12 h-12 mx-auto mb-4 vf-text-m" />
          <p className="vf-text-1 font-medium">No installment plans</p>
          <p className="vf-text-m mt-1">Create installment plans to split invoice payments over time.</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {installments.map((plan) => {
            const cfg = statusConfig[plan.status]
            const StatusIcon = cfg.icon
            const progress = plan.total_amount > 0 ? (plan.paid_amount / plan.total_amount) * 100 : 0

            return (
              <div key={plan.id} className="vf-bg-card vf-border rounded-lg p-5">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <p className="vf-text-1 font-medium">{plan.customer_name}</p>
                    <p className="vf-text-m text-sm">Invoice {plan.invoice_number}</p>
                  </div>
                  <span className={styles[STATUS_MODULE[plan.status] ?? "statusActive"]}>
                    <StatusIcon className="w-3 h-3" />
                    {cfg.label}
                  </span>
                </div>

                <div className="mb-3">
                  <div className="flex justify-between text-sm mb-1">
                    <span className="vf-text-m">{plan.completed_count} of {plan.installment_count} payments</span>
                    <span className="vf-text-1 font-medium">{plan.paid_amount.toLocaleString()} / {plan.total_amount.toLocaleString()} {plan.currency}</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all ${plan.status === "overdue" ? "bg-red-500" : "bg-blue-600"}`}
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>

                {plan.next_due_date && (
                  <p className="vf-text-m text-sm">
                    Next payment due: {new Date(plan.next_due_date).toLocaleDateString()}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
