"use client";

import { useEffect, useState } from "react";
import { Sun, Moon } from "lucide-react";

/**
 * ThemeToggle — toggles dark/light mode.
 * Reads/writes localStorage key "theme" and adds/removes the `dark` class
 * on <html>. Works without next-themes for a zero-dependency toggle.
 */
export default function ThemeToggle() {
  const [dark, setDark] = useState(false);

  // Initialise from localStorage (or system preference) on mount
  useEffect(() => {
    const stored = localStorage.getItem("theme");
    const prefersDark =
      stored === "dark" ||
      (!stored && window.matchMedia("(prefers-color-scheme: dark)").matches);
    setDark(prefersDark);
    document.documentElement.classList.toggle("dark", prefersDark);
  }, []);

  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  }

  return (
    <button
      onClick={toggle}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      className="flex h-8 w-8 items-center justify-center rounded-lg transition-colors vf-text-m hover:vf-text-1"
      style={{
        background: "var(--vf-bg-elevated)",
        border: "1px solid var(--vf-border)",
      }}
    >
      {dark ? (
        <Sun  className="h-4 w-4 text-amber-400" />
      ) : (
        <Moon className="h-4 w-4 text-indigo-400" />
      )}
    </button>
  );
}
