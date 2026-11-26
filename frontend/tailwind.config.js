/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Paleta provisória; na Fase 3 é derivada da logo da Kavria.
        ink: { 950: "#0b0d12", 900: "#11141b", 800: "#181c25", 700: "#232836", 600: "#2f3646" },
        brand: { 400: "#5eead4", 500: "#14b8a6", 600: "#0d9488" },
      },
      fontFamily: {
        sans: ["Inter", "Segoe UI", "Roboto", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
