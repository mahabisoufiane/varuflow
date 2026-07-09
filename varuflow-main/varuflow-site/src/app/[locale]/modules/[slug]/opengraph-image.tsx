import { MODULES } from "@/content/modules";
import { OG_SIZE, renderOg } from "@/lib/og";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "Varuflow module";

export function generateStaticParams() {
  return ["sv", "en"].flatMap((locale) => MODULES.map((m) => ({ locale, slug: m.slug })));
}

export default async function Image({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug } = await params;
  const loc = locale === "en" ? "en" : "sv";
  const m = MODULES.find((x) => x.slug === slug);
  return renderOg(m?.name[loc] ?? "Varuflow", m?.description[loc] ?? "");
}
