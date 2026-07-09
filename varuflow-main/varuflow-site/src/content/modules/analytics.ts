import type { Module } from "./types";

export const analytics: Module = {
  slug: "analytics",
  gate: "analytics",
  name: { sv: "Efterfrågeprognoser", en: "Demand forecasting" },
  description: {
    sv: "Prognoser per produkt utifrån din försäljningshistorik — beställ rätt mängd i rätt tid.",
    en: "Per-product forecasts from your own sales history — order the right amount at the right time.",
  },
  valueProp: {
    sv: "Beställ på fakta i stället för magkänsla. Prognoser per produkt, byggda på din egen försäljningshistorik.",
    en: "Order on facts instead of gut feeling. Per-product forecasts, built on your own sales history.",
  },
  capabilities: [
    {
      title: { sv: "Prognos per produkt", en: "Per-product forecasts" },
      description: { sv: "Förväntad efterfrågan per produkt och period — så att inköpen träffar rätt.", en: "Expected demand per product and period — so purchasing hits the mark." },
    },
    {
      title: { sv: "Rapporter och dashboards", en: "Reports and dashboards" },
      description: { sv: "Försäljning, marginal och lageromsättning i färdiga rapporter och egna dashboards.", en: "Sales, margin and stock turnover in ready-made reports and custom dashboards." },
    },
    {
      title: { sv: "Trender över tid", en: "Trends over time" },
      description: { sv: "Se säsongsmönster och trender innan de blir problem — eller missade möjligheter.", en: "Spot seasonality and trends before they become problems — or missed opportunities." },
    },
  ],
  related: ["inventory", "ai"],
};
