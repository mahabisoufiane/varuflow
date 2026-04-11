// File: mobile/constants/colors.ts
// Purpose: Color palette matching web design system exactly
// Used by: all screens and components

export const Colors = {
  dark: {
    bgPrimary:     "#0F172A",
    bgSurface:     "#1E293B",
    bgElevated:    "#263244",
    textPrimary:   "#F8FAFC",
    textSecondary: "#94A3B8",
    textMuted:     "#475569",
    accent:        "#6366F1",
    accentDark:    "#4F46E5",
    success:       "#10B981",
    warning:       "#F59E0B",
    error:         "#EF4444",
    border:        "rgba(255,255,255,0.08)",
    glassBg:       "rgba(30,41,59,0.85)",
    glassBorder:   "rgba(255,255,255,0.08)",
    tabBar:        "#1E293B",
  },
  light: {
    bgPrimary:     "#F8FAFC",
    bgSurface:     "#FFFFFF",
    bgElevated:    "#F1F5F9",
    textPrimary:   "#0F172A",
    textSecondary: "#475569",
    textMuted:     "#94A3B8",
    accent:        "#6366F1",
    accentDark:    "#4F46E5",
    success:       "#10B981",
    warning:       "#F59E0B",
    error:         "#EF4444",
    border:        "rgba(0,0,0,0.08)",
    glassBg:       "rgba(255,255,255,0.85)",
    glassBorder:   "rgba(0,0,0,0.08)",
    tabBar:        "#FFFFFF",
  },
} as const;

export type ColorScheme = keyof typeof Colors;
export type ThemeColors = typeof Colors.dark;
