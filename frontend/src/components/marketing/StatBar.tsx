// StatBar — trust signal strip: test count, feature count, uptime, etc.
interface Stat {
  value: string;
  label: string;
}

interface StatBarProps {
  stats?: Stat[];
}

const DEFAULT_STATS: Stat[] = [
  { value: "2,254", label: "Tests passing" },
  { value: "100+", label: "Features" },
  { value: "99.9%", label: "Uptime SLA" },
  { value: "EU", label: "Data residency" },
  { value: "14 days", label: "Free trial" },
  { value: "0 setup", label: "Onboarding fee" },
];

export default function StatBar({ stats = DEFAULT_STATS }: StatBarProps) {
  return (
    <div
      className="border-t border-b border-white/8 py-10"
      style={{ background: "rgba(255,255,255,0.03)" }}
    >
      <div className="mx-auto grid max-w-5xl grid-cols-2 gap-y-8 px-4 sm:grid-cols-3 lg:grid-cols-6">
        {stats.map((s) => (
          <div key={s.label} className="text-center">
            <p className="vf-text-1 text-2xl font-extrabold tabular-nums">{s.value}</p>
            <p className="vf-text-m mt-1 text-xs">{s.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
