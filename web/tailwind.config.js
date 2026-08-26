/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Severity palette, fixed across every view so a colour always means
        // the same thing.
        critical: "#ef4444",
        high: "#f97316",
        medium: "#eab308",
        low: "#64748b",
        pass: "#22c55e",
        ink: { 950: "#080b11", 900: "#0b0f17", 850: "#0f1520", 800: "#131a26", 700: "#1c2534", 600: "#233046" },
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
