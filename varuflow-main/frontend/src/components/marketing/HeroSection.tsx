// Marketing hero section — pure display, no client state needed.
import { Link } from "@/i18n/navigation";

interface CTAButton {
  href: string;
  label: string;
}

interface HeroSectionProps {
  eyebrow?: string;
  headline: string;
  subheadline: string;
  ctaPrimary: CTAButton;
  ctaSecondary?: CTAButton;
  /** YouTube embed ID or full URL to a self-hosted mp4 */
  videoId?: string;
}

export default function HeroSection({
  eyebrow,
  headline,
  subheadline,
  ctaPrimary,
  ctaSecondary,
  videoId,
}: HeroSectionProps) {
  return (
    <section className="relative overflow-hidden px-4 py-24 text-center">
      {/* Background radial glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 80% 60% at 50% -10%, rgba(37,99,235,0.18) 0%, transparent 70%)",
        }}
      />

      <div className="relative mx-auto max-w-3xl">
        {eyebrow && (
          <p className="mb-4 inline-block rounded-full border border-[var(--vf-brand-border)] bg-[var(--vf-brand-primary-subtle)] px-4 py-1 text-xs font-semibold uppercase tracking-widest text-[var(--vf-brand-primary-light)]">
            {eyebrow}
          </p>
        )}

        <h1 className="vf-text-1 text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl lg:text-6xl">
          {headline}
        </h1>

        <p className="vf-text-2 mx-auto mt-6 max-w-2xl text-lg leading-relaxed">
          {subheadline}
        </p>

        <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link
            href={ctaPrimary.href}
            className="vf-btn rounded-xl px-7 py-3 text-base font-semibold"
          >
            {ctaPrimary.label}
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

      {videoId && (
        <div className="relative mx-auto mt-16 max-w-4xl overflow-hidden rounded-2xl border border-white/10 shadow-2xl">
          <div className="aspect-video">
            <iframe
              src={`https://www.youtube-nocookie.com/embed/${videoId}?rel=0&modestbranding=1`}
              title="Varuflow product demo"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              className="h-full w-full border-0"
              loading="lazy"
            />
          </div>
        </div>
      )}
    </section>
  );
}
