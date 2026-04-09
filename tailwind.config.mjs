/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/**/*.{astro,html,js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        deep: "var(--color-deep)",
        deeper: "var(--color-deeper)",
        surface: "var(--color-surface)",
        card: "var(--color-card)",
        accent: "var(--color-accent)",
        secondary: "var(--color-secondary)",
        main: "var(--color-main)",
        dim: "var(--color-dim)",
      },
      fontFamily: {
        display: [
          "Outfit Variable",
          "Outfit",
          "system-ui",
          "sans-serif",
        ],
        sans: [
          "DM Sans Variable",
          "DM Sans",
          "system-ui",
          "sans-serif",
        ],
      },
      backgroundImage: {
        "grid-fade":
          "linear-gradient(to right, rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.03) 1px, transparent 1px)",
        "glow-orange":
          "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(249, 122, 18, 0.22), transparent 55%)",
        "glow-blue":
          "radial-gradient(ellipse 60% 40% at 85% 60%, rgba(49, 120, 198, 0.14), transparent 50%)",
      },
      boxShadow: {
        card: "0 16px 40px rgba(0, 0, 0, 0.42)",
        glow: "0 0 80px rgba(249, 122, 18, 0.12)",
      },
    },
  },
  plugins: [],
};
