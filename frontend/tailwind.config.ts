import type { Config } from "tailwindcss";

import { color, font, spacing } from "./design-system/tokens";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./design-system/**/*.{ts,tsx}",
    "./features/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    spacing,
    extend: {
      colors: {
        paper: color.paper,
        ink: color.ink,
        primary: {
          navy: color.primary.navy,
        },
      },
      fontFamily: {
        ui: [...font.ui],
        document: [...font.document],
      },
    },
  },
  plugins: [],
};

export default config;
