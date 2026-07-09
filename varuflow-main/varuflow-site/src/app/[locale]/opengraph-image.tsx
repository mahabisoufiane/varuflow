import { getTranslations } from "next-intl/server";
import { OG_SIZE, renderOg } from "@/lib/og";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "Varuflow";

export function generateStaticParams() {
  return [{ locale: "sv" }, { locale: "en" }];
}

export default async function Image({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "home" });
  return renderOg(t("hero.h1"), t("meta.description"));
}
