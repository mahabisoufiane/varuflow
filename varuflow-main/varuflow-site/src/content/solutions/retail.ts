import type { Solution } from "./types";

export const retail: Solution = {
  slug: "retail",
  eyebrow: { sv: "Byggt för modern handel", en: "Built for modern retail" },
  headline: {
    sv: "Sälj var som helst. Tappa aldrig koll på lagret.",
    en: "Sell anywhere. Never lose track of stock.",
  },
  subheadline: {
    sv: "Mobil kassa på valfri enhet, streckkodsskanning, lagersaldo i realtid i alla butiker och automatiska beställningspunkter.",
    en: "Mobile POS that works on any device, barcode scanning, real-time inventory across all locations, and automatic reorder points.",
  },
  painPoints: [
    {
      pain: { sv: "Kassan och lagret lever i olika system", en: "The register and the stock live in different systems" },
      detail: { sv: "Det som säljs i kassan syns inte i lagersystemet förrän någon räknar om för hand.", en: "What sells at the till doesn't show in the stock system until someone recounts by hand." },
      solution: { sv: "Kassan är byggd på lagret: varje köp räknar ner saldot i samma sekund, och återköp lägger tillbaka varan på rätt ställe.", en: "The register is built on top of inventory: every sale counts stock down the same second, and refunds put items back in the right place." },
      moduleSlug: "pos",
    },
    {
      pain: { sv: "Hyllor gapar tomma — eller är överfulla", en: "Shelves sit empty — or overflowing" },
      detail: { sv: "Utan beställningspunkter upptäcks bristen först när kunden frågar.", en: "Without reorder points, you only discover the gap when a customer asks." },
      solution: { sv: "Beställningspunkter per produkt larmar i tid, och prognoserna visar vad som kommer att sälja nästa månad.", en: "Per-product reorder points alert in time, and forecasts show what will sell next month." },
      moduleSlug: "inventory",
    },
    {
      pain: { sv: "Dagskassan stämmer inte", en: "The day's takings don't add up" },
      detail: { sv: "Dagsavslut i Excel och kvitton i en låda gör varje avstämning till ett detektivarbete.", en: "End-of-day in Excel and receipts in a drawer make every reconciliation detective work." },
      solution: { sv: "Z-rapporter per kassapass, alla betalsätt loggade, och kassaflödet samlat i finansvyn — utan kalkylblad.", en: "Z-reports per register session, every payment method logged, and cash flow collected in the finance view — no spreadsheets." },
      moduleSlug: "finance",
    },
  ],
  compliance: {
    sv: "Personuppgifter krypteras i vila och under överföring, och din data kan exporteras när som helst — som allt annat i Varuflow.",
    en: "Personal data is encrypted at rest and in transit, and your data can be exported at any time — like everything else in Varuflow.",
  },
};
