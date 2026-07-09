import type { Solution } from "./types";

export const wholesale: Solution = {
  slug: "wholesale",
  eyebrow: { sv: "Byggt för B2B-grossister", en: "Built for B2B wholesalers" },
  headline: {
    sv: "Dina B2B-kunder förtjänar en modern portal",
    en: "Your B2B customers deserve a modern portal",
  },
  subheadline: {
    sv: "Låt kunderna lägga ordrar, följa fakturor och se leveransstatus i en portal med er profil — medan ni sköter lager, kreditvillkor och e-fakturering från en instrumentpanel.",
    en: "Let customers place orders, track invoices, and see delivery status in a branded portal — while you manage inventory, credit terms, and e-invoicing from one dashboard.",
  },
  painPoints: [
    {
      pain: { sv: "Ordrar kommer via telefon, mejl och sms", en: "Orders arrive by phone, email and text" },
      detail: { sv: "Varje order måste skrivas av för hand — och fel smyger sig in på vägen.", en: "Every order has to be retyped by hand — and errors sneak in along the way." },
      solution: { sv: "Kundportalen låter kunderna beställa själva, med deras egna avtalspriser. Ordern landar direkt i lagret och faktureringen.", en: "The customer portal lets customers order themselves, at their own agreed prices. The order lands straight in inventory and invoicing." },
      moduleSlug: "inventory",
    },
    {
      pain: { sv: "Fakturering och betalningsbevakning tar dagar varje månad", en: "Invoicing and payment chasing eat days every month" },
      detail: { sv: "Manuell fakturering mot leveranser, och ingen hinner jaga förfallna betalningar.", en: "Manual invoicing against deliveries, and nobody has time to chase overdue payments." },
      solution: { sv: "Fakturor skapas ur ordrarna med rätt moms och OCR, e-faktura via Peppol ingår, och påminnelser går ut automatiskt.", en: "Invoices are created from the orders with correct VAT and OCR, Peppol e-invoicing included, and reminders go out automatically." },
      moduleSlug: "invoicing",
    },
    {
      pain: { sv: "Ingen vet vad som finns i lager förrän det är slut", en: "Nobody knows what's in stock until it runs out" },
      detail: { sv: "Sälj lovar bort varor som inte finns, och inköp beställer på känsla.", en: "Sales promises goods that aren't there, and purchasing orders on gut feeling." },
      solution: { sv: "Lagret uppdateras i realtid vid varje order, och efterfrågeprognoserna säger vad du ska beställa innan bristen uppstår.", en: "Stock updates in real time with every order, and demand forecasts tell you what to order before the shortage happens." },
      moduleSlug: "analytics",
    },
  ],
  compliance: {
    sv: "Personuppgifter krypteras i vila och under överföring, och din data kan exporteras när som helst — som allt annat i Varuflow.",
    en: "Personal data is encrypted at rest and in transit, and your data can be exported at any time — like everything else in Varuflow.",
  },
};
