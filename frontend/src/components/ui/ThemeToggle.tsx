// File: src/components/ui/ThemeToggle.tsx
// Purpose: Pill-shaped dark/light mode toggle with sliding indicator
// Used by: AppShell sidebar, auth pages, settings page

"use client";

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Avoid hydration mismatch — only render after mount
  useEffect(() => setMounted(true), []);
  if (!mounted) return <div className="h-9 w-20" />;

  const isDark = theme === "dark";

  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      className="relative flex h-9 w-20 items-center rounded-full border transition-all duration-300"
      style={{
        background: isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)",
        borderColor: isDark ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.12)",
      }}
    >
      {/* Sliding indicator */}
      <span
        className="absolute h-7 w-7 rounded-full shadow-md transition-all duration-300 ease-in-out"
        style={{
          left: isDark ? "4px" : "calc(100% - 32px)",
          background: isDark
            ? "linear-gradient(135deg, #6366F1, #4F46E5)"
            : "linear-gradient(135deg, #F59E0B, #F97316)",
        }}
      />

      {/* Moon icon */}
      <span
        className="relative z-10 flex h-full w-1/2 items-center justify-center text-sm transition-opacity duration-200"
        style={{ opacity: isDark ? 1 : 0.4 }}
      >
        🌙
      </span>

      {/* Sun icon */}
      <span
        className="relative z-10 flex h-full w-1/2 items-center justify-center text-sm transition-opacity duration-200"
        style={{ opacity: isDark ? 0.4 : 1 }}
      >
        ☀️
      </span>
    </button>
  );
}
