import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      // Matches apps/website's brand palette (src/app/globals.css) so the
      // staff dashboard and the guest-facing site read as one product.
      colors: {
        primary: { DEFAULT: "#1E3A2F", dark: "#12241C" },
        accent: { DEFAULT: "#A3704C", light: "#C69F7B" },
        charcoal: "#222222",
        ivory: "#FAF9F6",
        sand: "#EAE5D9",
      },
    },
  },
  plugins: [],
};

export default config;
