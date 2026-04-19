/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        syne: ["'Syne'", "sans-serif"],
        dm: ["'DM Sans'", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
      colors: {
        ink: "#0d0d0d",
        paper: "#f5f2eb",
        accent: "#e85a2a",
        accent2: "#2a6ee8",
        muted: "#8a8680",
        border: "#e2ddd6",
      },
    },
  },
  plugins: [],
};