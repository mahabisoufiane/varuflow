import type { Module } from "./types";

export const finance: Module = {
  slug: "finance",
  gate: "finance",
  name: { sv: "Koll på kassaflödet", en: "Cash flow visibility" },
  description: {
    sv: "Se inbetalningar, förfallna fakturor och prognos i samma vy — utan kalkylblad.",
    en: "Incoming payments, overdue invoices and forecast in one view — no spreadsheets.",
  },
  valueProp: {
    sv: "Vet alltid var pengarna är. Inbetalningar, utestående fakturor och prognos i en vy som uppdaterar sig själv.",
    en: "Always know where the money is. Incoming payments, outstanding invoices and forecast in one self-updating view.",
  },
  capabilities: [
    {
      title: { sv: "Kassaflödesprognos", en: "Cash flow forecast" },
      description: { sv: "Se förväntade in- och utbetalningar framåt i tiden — byggd på dina riktiga fakturor.", en: "See expected inflows and outflows ahead of time — built on your actual invoices." },
    },
    {
      title: { sv: "Förfallobevakning", en: "Overdue tracking" },
      description: { sv: "Förfallna fakturor markeras direkt och kan följas upp med en knapptryckning.", en: "Overdue invoices are flagged immediately and followed up with one click." },
    },
    {
      title: { sv: "Avstämning", en: "Reconciliation" },
      description: { sv: "Stäm av betalningar mot fakturor och håll bokföringsunderlaget rent.", en: "Match payments against invoices and keep your bookkeeping records clean." },
    },
  ],
  related: ["invoicing", "analytics"],
};
