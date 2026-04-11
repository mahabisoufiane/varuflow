// File: mobile/babel.config.js
// Purpose: Babel config — enables NativeWind (Tailwind for RN) + expo-router
// Used by: Metro bundler

module.exports = function (api) {
  api.cache(true);
  return {
    presets: [
      ["babel-preset-expo", { jsxImportSource: "nativewind" }],
    ],
    plugins: [
      "nativewind/babel",
    ],
  };
};
