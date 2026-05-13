import { LabelPrinter } from "@/components/inventory/LabelPrinter";
import { getTranslations } from "next-intl/server";

// Inventory → Labels page (Item 36).

export default async function LabelsPage() {
  const t = await getTranslations("labels");
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight vf-text-1">{t("title")}</h1>
        <p className="text-xs vf-text-m mt-0.5">{t("subtitle")}</p>
      </div>
      <LabelPrinter />
    </div>
  );
}
