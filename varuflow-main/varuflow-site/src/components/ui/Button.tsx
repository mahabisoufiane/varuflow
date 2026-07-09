import { Link } from "@/i18n/navigation";
import type { ComponentProps } from "react";

type Variant = "primary" | "secondary" | "ghost";

const styles: Record<Variant, string> = {
  primary:
    "bg-brand text-white hover:bg-brand-strong",
  secondary:
    "border border-line bg-paper text-ink hover:border-ink",
  ghost:
    "text-brand hover:text-brand-strong",
};

const base =
  "inline-flex items-center justify-center gap-2 rounded-full px-6 py-3 text-small font-semibold transition-colors";

export function Button({
  href,
  variant = "primary",
  className = "",
  children,
  ...rest
}: {
  href: ComponentProps<typeof Link>["href"];
  variant?: Variant;
  className?: string;
  children: React.ReactNode;
} & Omit<ComponentProps<typeof Link>, "href" | "className">) {
  return (
    <Link href={href} className={`${base} ${styles[variant]} ${className}`} {...rest}>
      {children}
    </Link>
  );
}
