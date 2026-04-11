// File: mobile/tailwind.config.js
// Purpose: NativeWind / Tailwind config for React Native
// Used by: all screens and components via className prop

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,jsx,ts,tsx}", "./components/**/*.{js,jsx,ts,tsx}"],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: {
        vf: {
          bg:        "#0F172A",
          surface:   "#1E293B",
          elevated:  "#263244",
          accent:    "#6366F1",
          success:   "#10B981",
          warning:   "#F59E0B",
          error:     "#EF4444",
        },
      },
    },
  },
  plugins: [],
};
