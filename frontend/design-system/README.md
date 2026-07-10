# Design system

Token layer for Provision. `tokens.ts` is the source of truth; `tailwind.config.ts`
derives its theme from it, and `tokens.css` mirrors it as CSS custom properties for
things Tailwind classes can't express at runtime (currently: density).

## Tokens

| Token | Value |
| --- | --- |
| `color.paper` | `#FAFAF7` — background |
| `color.ink` | `#1B1F27` — text |
| `color.primary.navy` | `#1A3A5C` — primary |
| `font.ui` | grotesque sans, for all UI chrome |
| `font.document` | serif, for memo/document body copy |
| numerals | tabular by default (`font-variant-numeric: tabular-nums`) |
| spacing | 4pt grid (`spacing[n] = n * 4px`) |
| density | `dense` (default) or `comfortable`, set via `<html data-density="...">` |

## Components

Shadcn/ui-style primitives live in `design-system/components/`. Generate new ones with
the shadcn CLI (`components.json` points `ui`/`components` aliases here) or hand-write
them following the existing `button.tsx` as a template — pure, unstyled-by-default,
variant props via `class-variance-authority`.
