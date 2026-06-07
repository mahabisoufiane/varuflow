"use client";

import { cx } from "@/lib/cx";
import styles from "./DataTable.module.scss";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T, index: number) => React.ReactNode;
  className?: string;
  hideBelow?: "sm" | "md";
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (row: T, index: number) => string;
  title?: string;
  actions?: React.ReactNode;
  density?: "compact" | "default" | "relaxed";
  emptyIcon?: React.ReactNode;
  emptyText?: string;
  emptySub?: string;
  onRowClick?: (row: T) => void;
}

export function DataTable<T>({
  columns,
  data,
  keyExtractor,
  title,
  actions,
  density = "default",
  emptyIcon,
  emptyText = "No data",
  emptySub,
  onRowClick,
}: DataTableProps<T>) {
  const densityCls = density === "compact" ? styles.compact : density === "relaxed" ? styles.relaxed : undefined;

  return (
    <div className={cx(styles.wrapper, densityCls)}>
      {(title || actions) && (
        <div className={styles.header}>
          {title && <h2 className={styles.title}>{title}</h2>}
          {actions && <div>{actions}</div>}
        </div>
      )}

      {data.length === 0 ? (
        <div className={styles.empty}>
          {emptyIcon && <div className={styles.emptyIcon}>{emptyIcon}</div>}
          <p className={styles.emptyText}>{emptyText}</p>
          {emptySub && <p className={styles.emptySub}>{emptySub}</p>}
        </div>
      ) : (
        <table className={styles.table}>
          <thead className={styles.thead}>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={cx(
                    styles.th,
                    col.hideBelow === "sm" && styles.hideSm,
                    col.hideBelow === "md" && styles.hideMd,
                    col.className,
                  )}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr
                key={keyExtractor(row, i)}
                className={cx(styles.tr, onRowClick && "cursor-pointer")}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={cx(
                      styles.td,
                      col.hideBelow === "sm" && styles.hideSm,
                      col.hideBelow === "md" && styles.hideMd,
                      col.className,
                    )}
                  >
                    {col.render(row, i)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
