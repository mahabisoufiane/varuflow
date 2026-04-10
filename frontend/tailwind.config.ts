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
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // Varuflow design system
        vf: {
          base:     "#0D0F14",
          surface:  "#13161E",
          elevated: "#1A1E29",
          indigo:   "#6366F1",
          "indigo-h": "#818CF8",
          success:  "#10B981",
          warning:  "#F59E0B",
          danger:   "#EF4444",
          "text-1": "#F1F5F9",
          "text-2": "#94A3B8",
          "text-m": "#475569",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card:     "0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)",
        elevated: "0 4px 24px rgba(0,0,0,0.4)",
        glow:     "0 0 20px rgba(99,102,241,0.15)",
        "glow-lg":"0 0 40px rgba(99,102,241,0.25)",
      },
      keyframes: {
        "fade-in": {
          "0%":   { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "slide-up": {
          "0%":   { opacity: "0", transform: "translateY(16px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-dot": {
          "0%, 100%": { opacity: "1" },
          "50%":      { opacity: "0.4" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        "bounce-dot": {
          "0%, 80%, 100%": { transform: "scale(0.6)", opacity: "0.4" },
          "40%":           { transform: "scale(1)",   opacity: "1"   },
        },
      },
      animation: {
        "fade-in":   "fade-in 0.2s ease-out both",
        "slide-up":  "slide-up 0.25s ease-out both",
        "pulse-dot": "pulse-dot 1.5s ease-in-out infinite",
        shimmer:     "shimmer 1.5s infinite",
        "bounce-dot":"bounce-dot 1.2s ease-in-out infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
export default config;
