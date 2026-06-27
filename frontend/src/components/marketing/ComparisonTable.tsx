// Varuflow vs {competitor} comparison table — server component.
import { Check, Minus } from "lucide-react";

export interface ComparisonRow {
  feature: string;
  varuflow: string;
  competitor: string;
}

interface ComparisonTableProps {
  competitorName: string;
  rows: ComparisonRow[];
}

export default function ComparisonTable({ competitorName, rows }: ComparisonTableProps) {
  return (
    <div className="mx-auto max-w-3xl overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/10">
            <th className="pb-3 text-left font-medium text-slate-400">Feature</th>
            <th className="pb-3 text-center">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-500/15 px-3 py-1 text-xs font-semibold text-indigo-300">
                Varuflow
              </span>
            </th>
            <th className="pb-3 text-center">
              <span className="text-xs font-semibold text-slate-500">{competitorName}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.feature} className="border-b border-white/5">
              <td className="py-3 text-slate-300">{row.feature}</td>
              <td className="py-3 text-center">{renderCell(row.varuflow, true)}</td>
              <td className="py-3 text-center">{renderCell(row.competitor, false)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function renderCell(val: string, positive: boolean) {
  const isYes = val.toLowerCase() === "yes" || val.toLowerCase() === "ja";
  const isNo = val.toLowerCase() === "no" || val.toLowerCase() === "nej";
  if (isYes)
    return (
      <Check
        className={`mx-auto h-4 w-4 ${positive ? "text-indigo-400" : "text-slate-500"}`}
      />
    );
  if (isNo) return <Minus className="mx-auto h-4 w-4 text-slate-700" />;
  return (
    <span className={positive ? "font-medium text-indigo-300" : "text-slate-400"}>
      {val}
    </span>
  );
}
