export function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-card border border-line bg-paper p-8 ${className}`}>
      {children}
    </div>
  );
}
