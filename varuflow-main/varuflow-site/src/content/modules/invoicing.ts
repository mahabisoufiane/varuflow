import type { Module } from "./types";

export const invoicing: Module = {
  slug: "invoicing",
  gate: "invoicing",
  name: { sv: "Fakturering enligt svenska regler", en: "SE-compliant invoicing" },
  description: {
    sv: "Fakturor med svensk moms, OCR-nummer och e-faktura (Peppol) — klart att skicka på sekunder.",
    en: "Invoices with Swedish VAT, OCR numbers and Peppol e-invoicing — ready to send in seconds.",
  },
  valueProp: {
    sv: "Fakturera på sekunder, med rätt moms från början. Byggd för svenska regler — inte anpassad till dem i efterhand.",
    en: "Invoice in seconds, with the right VAT from the start. Built for Swedish rules — not retrofitted to them.",
  },
  capabilities: [
    {
      title: { sv: "Svensk moms och OCR", en: "Swedish VAT and OCR" },
      description: { sv: "Momssatser, OCR-nummer och förfallodagar hanteras automatiskt på varje faktura.", en: "VAT rates, OCR numbers and due dates handled automatically on every invoice." },
    },
    {
      title: { sv: "E-faktura via Peppol", en: "Peppol e-invoicing" },
      description: { sv: "Skicka e-fakturor till företag och offentlig sektor direkt via Peppol-nätverket.", en: "Send e-invoices to companies and the public sector straight through the Peppol network." },
    },
    {
      title: { sv: "Påminnelser och kreditfakturor", en: "Reminders and credit notes" },
      description: { sv: "Automatiska betalningspåminnelser och kreditfakturor när något behöver rättas.", en: "Automatic payment reminders, and credit notes when something needs correcting." },
    },
  ],
  related: ["finance", "inventory"],
};
