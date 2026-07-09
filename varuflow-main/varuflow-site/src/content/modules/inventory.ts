import type { Module } from "./types";

export const inventory: Module = {
  slug: "inventory",
  gate: "inventory",
  name: { sv: "Lager i realtid", en: "Real-time inventory" },
  description: {
    sv: "Levande lagersaldo i alla lagerställen. Larm vid lågt saldo innan kunderna hinner märka något.",
    en: "Live stock across every warehouse. Low-stock alerts fire before customers notice.",
  },
  valueProp: {
    sv: "Sluta räkna lager i efterhand. Varje försäljning, inleverans och flytt uppdaterar saldot i samma sekund — i alla lagerställen.",
    en: "Stop counting stock after the fact. Every sale, delivery and transfer updates the balance the same second — across every warehouse.",
  },
  capabilities: [
    {
      title: { sv: "Flera lagerställen", en: "Multiple warehouses" },
      description: { sv: "Levande saldo per lagerställe med flyttar emellan — och ett samlat totalsaldo.", en: "Live balance per warehouse with transfers between them — and one combined total." },
    },
    {
      title: { sv: "Larm och beställningspunkter", en: "Alerts and reorder points" },
      description: { sv: "Sätt beställningspunkt per produkt och få larm innan hyllan gapar tom.", en: "Set a reorder point per product and get alerted before the shelf goes empty." },
    },
    {
      title: { sv: "Streckkoder & inventering", en: "Barcodes & stocktaking" },
      description: { sv: "Skanna EAN-koder med kamera eller USB-skanner — vid inleverans, försäljning och inventering.", en: "Scan EAN codes with a camera or USB scanner — on receiving, sale and stocktake." },
    },
  ],
  related: ["pos", "analytics"],
};
