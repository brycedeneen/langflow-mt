/**
 * Runtime-safe coercion for tag data coming from the server.
 *
 * The Flow and Template read shapes do not yet expose the new
 * flow_tag-backed tag list, so at the moment these helpers always
 * return []. When the backend starts returning `tags: TagRead[]` on
 * flow/template read responses, these helpers will pass them through
 * after validating the shape — so `TagChip` can trust its inputs.
 */

import type { TagRead } from "./index";
import { TAG_COLORS } from "./index";

export function isTagRead(value: unknown): value is TagRead {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.id === "string" &&
    typeof v.name === "string" &&
    typeof v.color === "string" &&
    TAG_COLORS.includes(v.color as (typeof TAG_COLORS)[number])
  );
}

/**
 * Safely pull a list of `TagRead` values from an unknown source (typically
 * the `tags` field on a server-side Flow or Template object that may not
 * yet expose the new shape).
 */
export function coerceTagList(raw: unknown): TagRead[] {
  if (!Array.isArray(raw)) return [];
  return raw.filter(isTagRead);
}
