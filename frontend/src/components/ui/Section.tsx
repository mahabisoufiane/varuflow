"use client";

import { type HTMLAttributes, type ReactNode } from "react";
import { cx } from "@/lib/cx";
import styles from "./Section.module.scss";

export interface SectionProps extends HTMLAttributes<HTMLDivElement> {
  children?: ReactNode;
}

export function Section({ className, children, ...props }: SectionProps) {
  return (
    <div className={cx(styles.section, className)} {...props}>
      {children}
    </div>
  );
}

export interface SectionHeaderProps extends HTMLAttributes<HTMLDivElement> {
  title?: string;
  description?: string;
  actions?: ReactNode;
  children?: ReactNode;
}

export function SectionHeader({ title, description, actions, className, children, ...props }: SectionHeaderProps) {
  return (
    <div className={cx(styles.header, className)} {...props}>
      {children || (
        <>
          <div>
            {title && <h2 className={styles.headerTitle}>{title}</h2>}
            {description && <p className={styles.headerDescription}>{description}</p>}
          </div>
          {actions && <div className={styles.headerActions}>{actions}</div>}
        </>
      )}
    </div>
  );
}

export interface SectionBodyProps extends HTMLAttributes<HTMLDivElement> {
  compact?: boolean;
  children?: ReactNode;
}

export function SectionBody({ compact, className, children, ...props }: SectionBodyProps) {
  return (
    <div className={cx(styles.body, compact && styles.bodyCompact, className)} {...props}>
      {children}
    </div>
  );
}

export function SectionFooter({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cx(styles.footer, className)} {...props}>
      {children}
    </div>
  );
}
