import { cn } from "@/lib/utils";

function Bone({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} />;
}

export function PageSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="flex-1 p-6 space-y-6">
      <div className="flex items-center justify-between">
        <Bone className="h-7 w-48" />
        <Bone className="h-9 w-28" />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="vf-card !p-4 space-y-2">
            <Bone className="h-3 w-20" />
            <Bone className="h-8 w-24" />
          </div>
        ))}
      </div>
      <div className="vf-card space-y-3">
        <Bone className="h-5 w-40" />
        {Array.from({ length: rows }).map((_, i) => (
          <Bone key={i} className="h-10 w-full" />
        ))}
      </div>
    </div>
  );
}
