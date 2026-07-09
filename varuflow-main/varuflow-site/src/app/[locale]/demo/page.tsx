import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { Container } from "@/components/ui/Container";
import { Section } from "@/components/ui/Section";
import { DemoForm } from "@/components/site/DemoForm";
import { pageMetadata } from "@/lib/seo";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "demo" });
  return pageMetadata({
    locale,
    path: "/demo",
    title: t("metaTitle"),
    description: t("metaDescription"),
  });
}

export default async function DemoPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("demo");

  return (
    <Section className="pt-16 sm:pt-24">
      <Container>
        <div className="mx-auto max-w-xl">
          <h1 className="font-display text-4xl font-bold tracking-tight text-ink">{t("title")}</h1>
          <p className="mt-4 text-body text-mist">{t("sub")}</p>
          <div className="mt-10">
            <DemoForm />
          </div>
        </div>
      </Container>
    </Section>
  );
}
