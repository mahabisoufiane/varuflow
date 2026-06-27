"use client";
// Custom ThemeProvider — replaces next-themes to avoid the React 19
// "Encountered a script tag while rendering React component" warning.
// next-themes v0.4.x injects an unfixable raw <script> into its component
// tree. We bypass this by handling FOUC via a beforeInteractive Script in
// layout.tsx and applying theme class entirely through useEffect here.

import { createContext, useContext, useEffect, useState, useCallback } from "react";

type Theme = "dark" | "light";

interface ThemeContextValue {
  theme: Theme;
  setTheme: (t: Theme) => void;
  resolvedTheme: Theme;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: "dark",
  setTheme: () => {},
  resolvedTheme: "dark",
});

export function useTheme() {
  return useContext(ThemeContext);
}

interface ThemeProviderProps {
  children: React.ReactNode;
  defaultTheme?: Theme;
  storageKey?: string;
  // Accept (and ignore) next-themes-compatible props so callers don't need changes
  attribute?: string;
  enableSystem?: boolean;
  scriptProps?: Record<string, unknown>;
}

export function ThemeProvider({
  children,
  defaultTheme = "light",
  storageKey = "varuflow-theme",
}: ThemeProviderProps) {
  const [theme, setThemeState] = useState<Theme>(defaultTheme);

  // On mount, read saved preference
  useEffect(() => {
    try {
      const saved = localStorage.getItem(storageKey) as Theme | null;
      if (saved === "light" || saved === "dark") {
        setThemeState(saved);
      }
    } catch {}
  }, [storageKey]);

  // Sync class to <html> whenever theme changes
  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove("light", "dark");
    root.classList.add(theme);
    try {
      localStorage.setItem(storageKey, theme);
    } catch {}
  }, [theme, storageKey]);

  const setTheme = useCallback((t: Theme) => setThemeState(t), []);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, resolvedTheme: theme }}>
      {children}
    </ThemeContext.Provider>
  );
}
