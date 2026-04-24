/**
 * Tailwind class names for the 10-value tag color palette.
 *
 * Kept in lockstep with `TagColor` (enum at ../index.ts) and the
 * `TAG_COLOR_VALUES` tuple in the alembic migration for the tag table.
 * If you add a new color, update all three places.
 */

import type { TagColor } from "./index";

export const TAG_COLOR_BG_MAP: Record<TagColor, string> = {
  slate: "bg-slate-500",
  red: "bg-red-500",
  orange: "bg-orange-500",
  amber: "bg-amber-500",
  green: "bg-green-500",
  teal: "bg-teal-500",
  sky: "bg-sky-500",
  blue: "bg-blue-500",
  violet: "bg-violet-500",
  pink: "bg-pink-500",
};
