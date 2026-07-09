import { useTranslations } from "next-intl";
import { Container } from "@/components/ui/Container";
import { Link } from "@/i18n/navigation";

export function Footer() {
  const t = useTranslations("footer");
  const tl = useTranslations("legal");

  return (
    <footer className="border-t border-line bg-ink py-16 text-white">
      <Container className="flex flex-col gap-10 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="font-display text-title font-bold">Varuflow</p>
          <p className="mt-2 max-w-xs text-small text-white/60">{t("tagline")}</p>
        </div>
        <div className="flex flex-col gap-3 text-small text-white/40 sm:items-end">
          <div className="flex gap-5">
            <Link href="/legal/privacy" className="hover:text-white/70">{tl("privacyTitle")}</Link>
            <Link href="/legal/terms" className="hover:text-white/70">{tl("termsTitle")}</Link>
          </div>
          <p>© {new Date().getFullYear()} Varuflow · {t("copyright")}</p>
        </div>
      </Container>
    </footer>
  );
}
