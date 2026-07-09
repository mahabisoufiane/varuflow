import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import { hasLocale, NextIntlClientProvider, type Messages } from "next-intl";
import { getMessages, getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import { SITE_URL } from "@/lib/seo";
import { ConsentGate } from "@/components/site/ConsentGate";
import { Header } from "@/components/site/Header";
import { Footer } from "@/components/site/Footer";
import "../globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const spaceGrotesk = Space_Grotesk({ subsets: ["latin"], variable: "--font-space-grotesk" });

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "home" });
  return {
    metadataBase: new URL(SITE_URL),
    title: { default: t("meta.title"), template: "%s · Varuflow" },
    description: t("meta.description"),
  };
}

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);

  // Only client components read messages from the provider; the sole client
  // island is PricingTiers (pricingPage namespace). Serializing everything
  // would ship every page's copy in the flight payload of every page.
  const all = await getMessages();
  // Namespaces used by client islands: PricingTiers, DemoForm/modal, ConsentGate.
  const clientMessages = {
    pricingPage: all.pricingPage,
    demo: all.demo,
    consent: all.consent,
  } as unknown as Messages;

  return (
    <html lang={locale} className={`${inter.variable} ${spaceGrotesk.variable}`}>
      <body>
        <NextIntlClientProvider messages={clientMessages}>
          <Header />
          <main>{children}</main>
          <Footer />
          <ConsentGate />
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
