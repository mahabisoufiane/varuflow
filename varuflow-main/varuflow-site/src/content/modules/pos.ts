import type { Module } from "./types";

export const pos: Module = {
  slug: "pos",
  gate: "pos",
  name: { sv: "Kassa (POS)", en: "Point of sale" },
  description: {
    sv: "Fullskärmskassa med streckkodsskanner, Swish, kort och kontant — kopplad direkt till lagret.",
    en: "Full-screen register with barcode scanning, Swish, card and cash — wired straight into inventory.",
  },
  valueProp: {
    sv: "En kassa som kan din butik. Skanna, ta betalt med Swish, kort eller kontant — och lagret räknas ner i samma sekund.",
    en: "A register that knows your store. Scan, take payment by Swish, card or cash — and stock counts down the same second.",
  },
  capabilities: [
    {
      title: { sv: "Skanner utan krångel", en: "Scanners that just work" },
      description: { sv: "USB- och Bluetooth-skannrar fungerar direkt — eller använd kameran på en surfplatta.", en: "USB and Bluetooth scanners work out of the box — or use the camera on a tablet." },
    },
    {
      title: { sv: "Swish, kort och kontant", en: "Swish, card and cash" },
      description: { sv: "Alla betalsätt svenska kunder förväntar sig, med växelräkning och kvitto som PDF.", en: "Every payment method Swedish customers expect, with change counting and PDF receipts." },
    },
    {
      title: { sv: "Z-rapporter och återköp", en: "Z-reports and refunds" },
      description: { sv: "Dagsavslut med Z-rapport, och återköp som återför lagret till rätt lagerställe.", en: "End-of-day Z-reports, and refunds that restore stock to the right warehouse." },
    },
  ],
  related: ["inventory", "finance"],
};
