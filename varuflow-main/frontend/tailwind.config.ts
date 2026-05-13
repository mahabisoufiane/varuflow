// File: tailwind.config.ts
// Purpose: Tailwind CSS configuration with full Varuflow design system — dark/light theming
// Used by: All components across the frontend

import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // shadcn tokens (kept for component compat)
        border:     "hsl(var(--border))",
        input:      "hsl(var(--input))",
        ring:       "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT:    "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT:    "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT:    "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT:    "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT:    "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT:    "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT:    "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // Varuflow semantic tokens — resolve to CSS variables for dark/light switching
        vf: {
          // Semantic (theme-aware)
          "bg-primary":    "var(--vf-bg-primary)",
          "bg-surface":    "var(--vf-bg-surface)",
          "bg-elevated":   "var(--vf-bg-elevated)",
          "text-primary":  "var(--vf-text-primary)",
          "text-secondary":"var(--vf-text-secondary)",
          "text-muted":    "var(--vf-text-muted)",
          // Static accent/status tokens
          accent:          "#6366F1",
          "accent-hover":  "#4F46E5",
          success:         "#10B981",
          warning:         "#F59E0B",
          danger:          "#EF4444",
          // Legacy aliases so existing pages don't break
          base:            "var(--vf-bg-primary)",
          surface:         "var(--vf-bg-surface)",
          elevated:        "var(--vf-bg-elevated)",
          indigo:          "#6366F1",
          "indigo-h":      "#818CF8",
          "text-1":        "var(--vf-text-primary)",
          "text-2":        "var(--vf-text-secondary)",
          "text-m":        "var(--vf-text-muted)",
        },
      },
      borderRadius: {
        lg:    "var(--radius)",
        md:    "calc(var(--radius) - 2px)",
        sm:    "calc(var(--radius) - 4px)",
        xl:    "16px",
        "2xl": "20px",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card:      "0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)",
        elevated:  "0 4px 24px rgba(0,0,0,0.4)",
        glow:      "0 0 20px rgba(99,102,241,0.15)",
        "glow-lg": "0 0 40px rgba(99,102,241,0.25)",
        "glow-btn":"inset 0 1px 0 rgba(255,255,255,0.1), 0 0 16px rgba(99,102,241,0.3)",
        glass:     "0 8px 32px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.05)",
      },
      keyframes: {
        "fade-in": {
          "0%":   { opacity: "0", transform: "translateY(8px)"  },
          "100%": { opacity: "1", transform: "translateY(0)"    },
        },
        "slide-up": {
          "0%":   { opacity: "0", transform: "translateY(16px)" },
          "100%": { opacity: "1", transform: "translateY(0)"    },
        },
        "pulse-dot": {
          "0%, 100%": { opacity: "1"   },
          "50%":      { opacity: "0.4" },
        },
        "orb-float": {
          "0%, 100%": { transform: "translate(0px, 0px) scale(1)"        },
          "33%":      { transform: "translate(30px, -20px) scale(1.05)"  },
          "66%":      { transform: "translate(-20px, 10px) scale(0.95)"  },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        "bounce-dot": {
          "0%, 80%, 100%": { transform: "scale(0.6)", opacity: "0.4" },
          "40%":           { transform: "scale(1)",   opacity: "1"   },
        },
        "bounce-subtle": {
          "0%, 100%": { transform: "translateY(0)"    },
          "50%":      { transform: "translateY(-6px)" },
        },
        "check-pop": {
          "0%":   { transform: "scale(0)", opacity: "0" },
          "60%":  { transform: "scale(1.2)"             },
          "100%": { transform: "scale(1)",  opacity: "1" },
        },
      },
      animation: {
        "fade-in":       "fade-in 0.2s ease-out both",
        "slide-up":      "slide-up 0.25s ease-out both",
        "pulse-dot":     "pulse-dot 1.5s ease-in-out infinite",
        "orb-float":     "orb-float 8s ease-in-out infinite",
        shimmer:         "shimmer 1.5s infinite",
        "bounce-dot":    "bounce-dot 1.2s ease-in-out infinite",
        "bounce-subtle": "bounce-subtle 2s ease-in-out infinite",
        "check-pop":     "check-pop 0.3s ease-out both",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
export default config;
