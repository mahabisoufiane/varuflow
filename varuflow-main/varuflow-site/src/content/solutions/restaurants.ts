import type { Solution } from "./types";

export const restaurants: Solution = {
  slug: "restaurants",
  eyebrow: { sv: "Byggt för restauranger & kaféer", en: "Built for restaurants & cafés" },
  headline: {
    sv: "Matsalen möter köket",
    en: "Front of house meets back of house",
  },
  subheadline: {
    sv: "Bordskassa, onlinebokning, lagerkoll i köket och leverantörsbeställningar — sammankopplat så att inget faller mellan stolarna.",
    en: "Table POS, online reservations, kitchen stock management, and supplier ordering — linked together so nothing slips through the cracks.",
  },
  painPoints: [
    {
      pain: { sv: "Råvaror tar slut mitt i servicen", en: "Ingredients run out mid-service" },
      detail: { sv: "Ingen vet vad som finns i kylen förrän kocken öppnar dörren.", en: "Nobody knows what's in the fridge until the chef opens the door." },
      solution: { sv: "Lagerkoll på råvaror med larm vid lågt saldo — och leverantörsbeställningar direkt ur systemet innan det blir kris.", en: "Stock control on ingredients with low-level alerts — and supplier orders straight from the system before it becomes a crisis." },
      moduleSlug: "inventory",
    },
    {
      pain: { sv: "Kassan är byggd för butik, inte för servering", en: "The register was built for shops, not service" },
      detail: { sv: "Notor som ska delas, bord som byter gäster, och en kö vid disken.", en: "Bills that need splitting, tables that change guests, and a queue at the counter." },
      solution: { sv: "En snabb kassa med Swish, kort och kontant och kvitto på sekunder — byggd för tempot vid disken.", en: "A fast register with Swish, card and cash and receipts in seconds — built for the pace at the counter." },
      moduleSlug: "pos",
    },
    {
      pain: { sv: "Marginalen försvinner någonstans mellan inköp och nota", en: "Margin disappears somewhere between purchasing and the bill" },
      detail: { sv: "Råvarupriser rör sig varje vecka men menypriserna sätts en gång per år.", en: "Ingredient prices move every week but menu prices are set once a year." },
      solution: { sv: "Kassaflödet och marginalerna syns löpande i finansvyn, och AI-rådgivaren flaggar när en marginal börjar läcka.", en: "Cash flow and margins are visible continuously in the finance view, and the AI advisor flags when a margin starts to leak." },
      moduleSlug: "finance",
    },
  ],
  compliance: {
    sv: "Personuppgifter krypteras i vila och under överföring, och din data kan exporteras när som helst — som allt annat i Varuflow.",
    en: "Personal data is encrypted at rest and in transit, and your data can be exported at any time — like everything else in Varuflow.",
  },
};
