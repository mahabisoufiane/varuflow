import { getTranslations } from "next-intl/server";
import { OG_SIZE, renderOg } from "@/lib/og";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "Book a Varuflow demo";

export function generateStaticParams() {
  return [{ locale: "sv" }, { locale: "en" }];
}

export default async function Image({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "demo" });
  return renderOg(t("metaTitle"), t("metaDescription"));
}
