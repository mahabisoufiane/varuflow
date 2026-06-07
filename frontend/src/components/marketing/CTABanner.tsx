// CTABanner — repeating call-to-action section. Use at page bottom.
import { Link } from "@/i18n/navigation";
import { ArrowRight } from "lucide-react";

interface CTAButton {
  href: string;
  label: string;
}

interface CTABannerProps {
  headline: string;
  subheadline?: string;
  ctaPrimary: CTAButton;
  ctaSecondary?: CTAButton;
}

export default function CTABanner({ headline, subheadline, ctaPrimary, ctaSecondary }: CTABannerProps) {
  return (
    <section
      className="relative overflow-hidden px-4 py-20 text-center"
      style={{
        background:
          "radial-gradient(ellipse 80% 60% at 50% 50%, rgba(74,108,247,0.15) 0%, transparent 70%)",
      }}
    >
      <div className="mx-auto max-w-2xl">
        <h2 className="vf-text-1 text-3xl font-extrabold tracking-tight sm:text-4xl">
          {headline}
        </h2>
        {subheadline && (
          <p className="vf-text-2 mx-auto mt-4 max-w-xl text-base leading-relaxed">
            {subheadline}
          </p>
        )}

        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link
            href={ctaPrimary.href}
            className="vf-btn inline-flex items-center gap-2 rounded-xl px-7 py-3 text-base font-semibold"
          >
            {ctaPrimary.label}
            <ArrowRight className="h-4 w-4" />
          </Link>
          {ctaSecondary && (
            <Link
              href={ctaSecondary.href}
              className="vf-btn-ghost rounded-xl px-7 py-3 text-base font-semibold"
            >
              {ctaSecondary.label}
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}
