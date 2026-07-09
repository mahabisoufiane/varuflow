export function Section({
  children,
  shaded = false,
  className = "",
}: {
  children: React.ReactNode;
  /** Alternating band background for rhythm between sections. */
  shaded?: boolean;
  className?: string;
}) {
  return (
    <section className={`${shaded ? "bg-paper-shade" : "bg-paper"} py-20 sm:py-28 ${className}`}>
      {children}
    </section>
  );
}
