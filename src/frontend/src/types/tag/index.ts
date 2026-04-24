export const TAG_COLORS = [
  "slate",
  "red",
  "orange",
  "amber",
  "green",
  "teal",
  "sky",
  "blue",
  "violet",
  "pink",
] as const;

export type TagColor = (typeof TAG_COLORS)[number];

export interface TagRead {
  id: string;
  name: string;
  color: TagColor;
  description: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface TagWrite {
  name: string;
  color: TagColor;
  description?: string | null;
}
