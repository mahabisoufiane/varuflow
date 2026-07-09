import { SOLUTIONS } from "@/content/solutions";
import { OG_SIZE, renderOg } from "@/lib/og";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "Varuflow solution";

export function generateStaticParams() {
  return ["sv", "en"].flatMap((locale) => SOLUTIONS.map((s) => ({ locale, slug: s.slug })));
}

export default async function Image({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug } = await params;
  const loc = locale === "en" ? "en" : "sv";
  const s = SOLUTIONS.find((x) => x.slug === slug);
  return renderOg(s?.headline[loc] ?? "Varuflow", s?.eyebrow[loc] ?? "");
}
