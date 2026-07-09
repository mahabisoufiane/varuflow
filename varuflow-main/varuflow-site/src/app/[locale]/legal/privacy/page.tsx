import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { Container } from "@/components/ui/Container";
import { Section } from "@/components/ui/Section";
import { pageMetadata } from "@/lib/seo";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "legal" });
  return {
    ...pageMetadata({
      locale,
      path: "/legal/privacy",
      title: t("privacyTitle"),
      description: t("underReview"),
    }),
    // Placeholder copy — keep out of the index until legal review lands.
    robots: { index: false, follow: true },
  };
}

export default async function LegalPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("legal");

  return (
    <Section className="pt-16 sm:pt-24">
      <Container>
        <div className="mx-auto max-w-2xl">
          <h1 className="font-display text-4xl font-bold tracking-tight text-ink">
            {t("privacyTitle")}
          </h1>
          <p className="mt-6 text-body text-mist">{t("underReview")}</p>
          <Link href="/" className="mt-8 inline-block text-body font-semibold text-brand hover:text-brand-strong">
            {t("backHome")} →
          </Link>
        </div>
      </Container>
    </Section>
  );
}
