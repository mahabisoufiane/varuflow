// File: src/components/console/ContentPanel.tsx
// Purpose: Region 3 of the operator console — the center detail area. A REUSABLE,
// generic component that renders a data table for a category selection and a
// detail view (Sheet) for an item selection, using the existing shadcn/ui Table
// and the new ui/sheet. It is presentational only: pages opt into it and keep
// owning their data fetching, so all existing routing/business logic is intact.
//
// Reuse: ui/table (Table, TableHeader, …), ui/sheet (detail), ui/skeleton
// (loading). No new table engine is introduced.
//
// Example (inside an existing page):
//   const [sel, setSel] = useState<Customer | null>(null);
//   <ContentPanel<Customer>
//     title={t("customers.title")}
//     rows={customers}
//     getRowId={(c) => c.id}
//     columns={[
//       { key: "name", header: t("customers.name") },
//       { key: "orders", header: t("customers.orders"), render: (c) => c.order_count },
//     ]}
//     selected={sel}
//     onSelect={setSel}
//     detailTitle={(c) => c.name}
//     detailFields={[{ label: t("customers.email"), render: (c) => c.email }]}
//   />

"use client";

import * as React from "react";
import { useTranslations } from "next-intl";

import { cn } from "@/lib/utils";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";

export interface ColumnDef<T> {
  key: string;
  header: string;
  /** Custom cell renderer; defaults to String(row[key]). */
  render?: (row: T) => React.ReactNode;
  className?: string;
}

export interface DetailField<T> {
  label: string;
  render: (row: T) => React.ReactNode;
}

export interface ContentPanelProps<T> {
  title: string;
  columns: ColumnDef<T>[];
  rows: T[];
  getRowId: (row: T) => string | number;
  loading?: boolean;
  /** Optional caller-translated empty message (else uses console.panel.empty). */
  emptyMessage?: string;
  /** Optional actions (e.g. a +New button) rendered in the panel header. */
  toolbar?: React.ReactNode;
  /** Controlled row selection → opens the detail Sheet. Omit to disable detail. */
  selected?: T | null;
  onSelect?: (row: T | null) => void;
  detailTitle?: (row: T) => string;
  detailDescription?: (row: T) => string;
  detailFields?: DetailField<T>[];
  /** Full custom detail body (overrides detailFields). */
  renderDetail?: (row: T) => React.ReactNode;
  /** Hide the built-in title/count header (e.g. when the host page has its own). */
  hideHeader?: boolean;
  /** Compact ~34px rows (Fortnox-grade density). Default true for list screens. */
  dense?: boolean;
  className?: string;
}

export function ContentPanel<T>({
  title,
  columns,
  rows,
  getRowId,
  loading = false,
  emptyMessage,
  toolbar,
  selected,
  onSelect,
  detailTitle,
  detailDescription,
  detailFields,
  renderDetail,
  hideHeader = false,
  dense = true,
  className,
}: ContentPanelProps<T>) {
  const t = useTranslations("console");
  const selectable = typeof onSelect === "function";
  const selectedId = selected != null ? getRowId(selected) : null;

  return (
    <section className={cn("flex h-full flex-col bg-background", className)}>
      {/* Panel header */}
      {!hideHeader && (
        <div className="flex items-center justify-between gap-2 border-b px-4 py-3">
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold text-foreground">{title}</h2>
            {!loading && (
              <p className="text-xs text-muted-foreground">
                {rows.length} {t("panel.rowsLabel")}
              </p>
            )}
          </div>
          {toolbar}
        </div>
      )}

      {/* Table (category view) */}
      <div className="flex-1 overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map((c) => (
                <TableHead key={c.key} className={cn(dense && "h-9 px-3 text-xs", c.className)}>
                  {c.header}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              Array.from({ length: 6 }).map((_, i) => (
                <TableRow key={`sk-${i}`}>
                  {columns.map((c) => (
                    <TableCell key={c.key} className={cn(dense && "px-3 py-2")}>
                      <Skeleton className="h-4 w-24" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="py-10 text-center text-sm text-muted-foreground">
                  {emptyMessage ?? t("panel.empty")}
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row) => {
                const id = getRowId(row);
                return (
                  <TableRow
                    key={id}
                    data-state={selectedId === id ? "selected" : undefined}
                    onClick={selectable ? () => onSelect!(row) : undefined}
                    className={cn(selectable && "cursor-pointer")}
                  >
                    {columns.map((c) => (
                      <TableCell key={c.key} className={cn(dense && "px-3 py-2", c.className)}>
                        {c.render ? c.render(row) : String((row as Record<string, unknown>)[c.key] ?? "")}
                      </TableCell>
                    ))}
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>

      {/* Detail view (item selection) */}
      {selectable && (
        <Sheet open={selected != null} onOpenChange={(open) => !open && onSelect!(null)}>
          <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-md">
            <SheetHeader>
              <SheetTitle>
                {selected && detailTitle ? detailTitle(selected) : t("panel.detailTitle")}
              </SheetTitle>
              {selected && detailDescription && (
                <SheetDescription>{detailDescription(selected)}</SheetDescription>
              )}
            </SheetHeader>
            <div className="px-4 pb-6">
              {selected &&
                (renderDetail ? (
                  renderDetail(selected)
                ) : (
                  <dl className="divide-y">
                    {detailFields?.map((f, i) => (
                      <div key={i} className="grid grid-cols-3 gap-2 py-2.5">
                        <dt className="text-xs font-medium text-muted-foreground">{f.label}</dt>
                        <dd className="col-span-2 text-sm text-foreground">{f.render(selected)}</dd>
                      </div>
                    ))}
                  </dl>
                ))}
            </div>
          </SheetContent>
        </Sheet>
      )}
    </section>
  );
}

export default ContentPanel;
