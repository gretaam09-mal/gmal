/**
 * Provision design tokens — single source of truth.
 *
 * tailwind.config.ts and design-system/tokens.css both derive from this
 * file. Change values here, not in either of those.
 */

export const color = {
  paper: "#FAFAF7",
  ink: "#1B1F27",
  primary: {
    navy: "#1A3A5C",
  },
} as const;

export const font = {
  /** Grotesque sans for all UI chrome: nav, buttons, labels, tables. */
  ui: ["Inter", "Helvetica Neue", "Arial", "sans-serif"],
  /** Serif for document/memo body copy — the thing a partner prints. */
  document: ["Source Serif 4", "Georgia", "serif"],
} as const;

export const numeric = {
  variant: "tabular-nums",
} as const;

/** 4pt spacing grid. Keys are multiples of the 4px base unit. */
export const spacing = Object.fromEntries(
  Array.from({ length: 25 }, (_, step) => [String(step), `${step * 4}px`]),
) as Record<string, string>;

export type Density = "dense" | "comfortable";

/** Row/control height and padding multipliers per density mode. */
export const density: Record<Density, { padding: number; lineHeight: number }> = {
  dense: { padding: 1, lineHeight: 1.3 },
  comfortable: { padding: 1.5, lineHeight: 1.5 },
};

export const defaultDensity: Density = "dense";
