import type { Config } from "tailwindcss";

// Design plan:
// Color - bg #FFFFFF, ink #1A1D21 (charcoal, not flat #111), brand #FFC53D
//   (confident yellow, not neon), brand-deep #E8A100 (hover/pressed),
//   neutral #F4F5F7 (section backgrounds), border #E3E5E9, and functional
//   green/red/blue reserved for status only.
// Type - Manrope for display/headlines (geometric, confident weight range),
//   Public Sans for body/UI (built for government/financial digital
//   services - legible, unpretentious, fits an insurance product's need
//   to feel plain-spoken rather than salesy).
// Layout - left-aligned, asymmetric hero (headline left, interactive
//   product-selector panel right) rather than centered hero + gradient.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#FFFFFF",
        ink: "#1A1D21",
        "ink-soft": "#565B64",
        brand: {
          DEFAULT: "#FFC53D",
          deep: "#E8A100",
          tint: "#FFF3D6",
        },
        neutral: {
          DEFAULT: "#F4F5F7",
          border: "#E3E5E9",
        },
        status: {
          success: "#1F9254",
          error: "#C5432B",
          info: "#2563EB",
        },
      },
      fontFamily: {
        display: ["var(--font-manrope)", "sans-serif"],
        body: ["var(--font-public-sans)", "sans-serif"],
      },
      borderRadius: {
        card: "16px",
        control: "10px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(26,29,33,0.04), 0 8px 24px rgba(26,29,33,0.06)",
      },
      maxWidth: {
        prose: "72ch",
      },
    },
  },
  plugins: [],
};

export default config;
