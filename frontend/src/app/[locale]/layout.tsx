import Script from "next/script";
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import { Toaster } from "@/components/ui/sonner";
import SentryInit from "@/components/app/SentryInit";
import "../globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "Varuflow — Lagerstyrning för svenska företag",
  description:
    "Varuflow hjälper svenska grossister att hantera lager, fakturering och kassaflöde från ett enda ställe. Integrerat med Fortnox.",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Varuflow",
  },
  other: {
    "mobile-web-app-capable": "yes",
  },
};

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

  if (!routing.locales.includes(locale as (typeof routing.locales)[number])) {
    notFound();
  }

  const messages = await getMessages();

  return (
    <html lang={locale} className={inter.variable}>
      <head>
        <meta name="theme-color" content="#1a2332" />
        <link rel="apple-touch-icon" href="/icon.svg" />
      </head>
      <body className="font-sans antialiased" suppressHydrationWarning>
        <NextIntlClientProvider messages={messages}>
          <SentryInit />
          {children}
          <Toaster position="bottom-right" richColors />
        </NextIntlClientProvider>
        {process.env.NEXT_PUBLIC_SENTRY_DSN && (
          <Script
            src="https://browser.sentry-cdn.com/8.0.0/bundle.min.js"
            strategy="afterInteractive"
          />
        )}
        <Script id="sw-register" strategy="afterInteractive">{`
          if ('serviceWorker' in navigator) {
            window.addEventListener('load', function() {
              navigator.serviceWorker.register('/sw.js');
            });
          }
        `}</Script>
      </body>
    </html>
  );
}
