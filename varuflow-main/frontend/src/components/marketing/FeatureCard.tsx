// Feature card — icon + title + description, optionally with a screenshot alt text placeholder.
import type { ReactNode } from "react";

interface FeatureCardProps {
  icon: ReactNode;
  title: string;
  description: string;
  badge?: string;
}

export default function FeatureCard({ icon, title, description, badge }: FeatureCardProps) {
  return (
    <div className="group relative rounded-2xl border border-white/10 bg-white/5 p-6 transition-colors hover:border-white/20 hover:bg-white/[0.07]">
      {badge && (
        <span className="absolute right-4 top-4 rounded-full bg-[var(--vf-brand-primary-soft)] px-2.5 py-0.5 text-xs font-semibold text-[var(--vf-brand-primary-light)]">
          {badge}
        </span>
      )}
      <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--vf-brand-primary-soft)] text-[var(--vf-brand-primary-light)]">
        {icon}
      </div>
      <h3 className="vf-text-1 mb-2 text-base font-semibold">{title}</h3>
      <p className="vf-text-2 text-sm leading-relaxed">{description}</p>
    </div>
  );
}
