// File: src/components/console/TaskDrawerContext.tsx
// Purpose: Shared state for the console's Task/Activity drawer (region 4).
// Holds (a) client-side optimistic tasks that any action can push — e.g. an
// invoice-send or stock-sync button reports "running" then "success"/"failed" —
// and (b) the drawer's open/collapsed state. Remote feed polling lives in
// TaskDrawer itself so this context never re-renders on every poll.

"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

export type TaskStatus = "pending" | "running" | "success" | "failed";

export interface ConsoleTask {
  id: string;
  label: string;
  status: TaskStatus;
  /** Where it came from — "local" = optimistic, "job"/"audit" = polled feed. */
  source: "local" | "job" | "audit";
  createdAt: string; // ISO 8601
  detail?: string;
}

interface TaskDrawerValue {
  tasks: ConsoleTask[]; // local/optimistic tasks only
  isOpen: boolean;
  setOpen: (open: boolean) => void;
  toggle: () => void;
  /** Add or replace (by id) a local task. */
  pushTask: (task: Omit<ConsoleTask, "source" | "createdAt"> & Partial<Pick<ConsoleTask, "createdAt">>) => void;
  /** Patch an existing local task (e.g. running → success). */
  updateTask: (id: string, patch: Partial<Omit<ConsoleTask, "id">>) => void;
  /** Remove finished (success/failed) local tasks. */
  clearFinished: () => void;
}

const TaskDrawerContext = createContext<TaskDrawerValue | null>(null);

export function TaskDrawerProvider({ children }: { children: React.ReactNode }) {
  const [tasks, setTasks] = useState<ConsoleTask[]>([]);
  const [isOpen, setIsOpen] = useState(false);

  const pushTask = useCallback<TaskDrawerValue["pushTask"]>((task) => {
    const entry: ConsoleTask = { source: "local", createdAt: new Date().toISOString(), ...task };
    setTasks((prev) => {
      const existing = prev.findIndex((t) => t.id === entry.id);
      if (existing >= 0) {
        const next = prev.slice();
        next[existing] = { ...next[existing], ...entry };
        return next;
      }
      return [entry, ...prev];
    });
    setIsOpen(true); // surface progress immediately
  }, []);

  const updateTask = useCallback<TaskDrawerValue["updateTask"]>((id, patch) => {
    setTasks((prev) => prev.map((t) => (t.id === id ? { ...t, ...patch } : t)));
  }, []);

  const clearFinished = useCallback(() => {
    setTasks((prev) => prev.filter((t) => t.status === "pending" || t.status === "running"));
  }, []);

  const value = useMemo<TaskDrawerValue>(
    () => ({
      tasks,
      isOpen,
      setOpen: setIsOpen,
      toggle: () => setIsOpen((o) => !o),
      pushTask,
      updateTask,
      clearFinished,
    }),
    [tasks, isOpen, pushTask, updateTask, clearFinished]
  );

  return <TaskDrawerContext.Provider value={value}>{children}</TaskDrawerContext.Provider>;
}

export function useTaskDrawer(): TaskDrawerValue {
  const ctx = useContext(TaskDrawerContext);
  if (!ctx) throw new Error("useTaskDrawer must be used within <TaskDrawerProvider> (ConsoleShell).");
  return ctx;
}
