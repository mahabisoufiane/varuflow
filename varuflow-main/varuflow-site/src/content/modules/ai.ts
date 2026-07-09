import type { Module } from "./types";

export const ai: Module = {
  slug: "ai",
  gate: "ai",
  name: { sv: "AI-rådgivare", en: "AI advisor" },
  description: {
    sv: "Dagliga åtgärdskort: vad som håller på att ta slut, vem som borde påminnas och var marginalen läcker.",
    en: "Daily action cards: what is about to run out, who needs a reminder, where margin is leaking.",
  },
  valueProp: {
    sv: "En kollega som läser alla siffror varje natt. Konkreta åtgärdskort i stället för rapporter du inte hinner öppna.",
    en: "A colleague who reads all the numbers every night. Concrete action cards instead of reports you never open.",
  },
  capabilities: [
    {
      title: { sv: "Åtgärdskort varje dag", en: "Action cards every day" },
      description: { sv: "Lågt lager, förfallna fakturor, marginalläckage — som förslag du kan agera på direkt.", en: "Low stock, overdue invoices, margin leaks — as suggestions you can act on immediately." },
    },
    {
      title: { sv: "Påminnelser med ett klick", en: "One-click follow-ups" },
      description: { sv: "Skicka betalningspåminnelser och utkast till inköpsordrar direkt från kortet.", en: "Send payment reminders and draft purchase orders straight from the card." },
    },
    {
      title: { sv: "Fråga din data", en: "Ask your data" },
      description: { sv: "Ställ frågor på svenska om lager, försäljning och kunder — få svar ur dina egna siffror.", en: "Ask questions in plain language about stock, sales and customers — answered from your own numbers." },
    },
  ],
  related: ["analytics", "finance"],
};
