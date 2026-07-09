import { ChevronDown } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Container } from "@/components/ui/Container";
import { MODULES } from "@/content/modules";
import { SOLUTIONS } from "@/content/solutions";
import { LocaleSwitcher } from "./LocaleSwitcher";

const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? "https://varuflow.vercel.app";

/** CSS-only dropdown: opens on hover and on keyboard focus (focus-within),
 *  no client JS. Server component — items come straight from content/. */
function Dropdown({
  label,
  items,
}: {
  label: string;
  items: { href: string; title: string; description: string }[];
}) {
  return (
    <div className="group relative">
      <button
        type="button"
        className="flex items-center gap-1 py-2 text-small font-medium text-ink-soft hover:text-ink"
      >
        {label}
        <ChevronDown className="h-3.5 w-3.5 transition-transform group-hover:rotate-180" />
      </button>
      <div className="invisible absolute left-1/2 top-full z-50 w-80 -translate-x-1/2 pt-2 opacity-0 transition-all group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100">
        <div className="rounded-card border border-line bg-paper p-2 shadow-lg">
          {items.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="block rounded-lg px-3 py-2.5 hover:bg-paper-shade"
            >
              <p className="text-small font-semibold text-ink">{item.title}</p>
              <p className="mt-0.5 line-clamp-1 text-small text-mist">{item.description}</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

export function Header() {
  const t = useTranslations("nav");
  const locale = useLocale();
  const loc: "sv" | "en" = locale === "en" ? "en" : "sv";

  const moduleItems = MODULES.map((m) => ({
    href: `/modules/${m.slug}`,
    title: m.name[loc],
    description: m.description[loc],
  }));
  const solutionItems = SOLUTIONS.map((s) => ({
    href: `/solutions/${s.slug}`,
    title: s.eyebrow[loc],
    description: s.headline[loc],
  }));

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-paper/95 backdrop-blur">
      <Container className="flex h-16 items-center justify-between">
        <Link href="/" className="font-display text-title font-bold tracking-tight text-ink">
          Varuflow
        </Link>
        <nav className="hidden items-center gap-6 md:flex">
          <Dropdown label={t("modules")} items={moduleItems} />
          <Dropdown label={t("solutions")} items={solutionItems} />
          <Link href="/pricing" className="py-2 text-small font-medium text-ink-soft hover:text-ink">
            {t("pricing")}
          </Link>
        </nav>
        <div className="flex items-center gap-3 sm:gap-6">
          <LocaleSwitcher />
          {/* CTA goes to the app's signup — external, plain anchor on purpose */}
          <a
            href={`${APP_URL}/sv/auth/signup`}
            className="inline-flex items-center whitespace-nowrap rounded-full bg-brand px-3.5 py-2 text-xs font-semibold text-white transition-colors hover:bg-brand-strong sm:px-5 sm:py-2.5 sm:text-small"
          >
            <span className="sm:hidden">{t("ctaShort")}</span>
            <span className="hidden sm:inline">{t("cta")}</span>
          </a>
        </div>
      </Container>
    </header>
  );
}
