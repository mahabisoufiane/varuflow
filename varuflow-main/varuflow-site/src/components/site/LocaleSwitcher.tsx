import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";

/** Server component: renders both locales, current one emphasized.
 *  Links point at the localized home — pathname-preserving switching
 *  needs a client component (usePathname) and can come with real pages. */
export function LocaleSwitcher() {
  const locale = useLocale();
  const t = useTranslations("localeSwitcher");

  return (
    <nav aria-label="Language" className="flex items-center gap-1 text-small">
      {routing.locales.map((l, i) => (
        <span key={l} className="flex items-center gap-1">
          {i > 0 && <span className="text-line">/</span>}
          <Link
            href="/"
            locale={l}
            className={l === locale ? "font-semibold text-ink" : "text-mist hover:text-ink"}
          >
            {t(l)}
          </Link>
        </span>
      ))}
    </nav>
  );
}
