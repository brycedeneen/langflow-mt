export type Category = {
  id: string;
  name: string;
  icon: string;
  color: string;
  description: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export type TemplateRead = {
  id: string;
  name: string;
  description: string | null;
  icon: string | null;
  gradient: string | null;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
  scope: "platform" | "org";
  org_id: string | null;
  created_by: string | null;
  categories: Category[];
};

export type TemplateReadDetail = TemplateRead & {
  nodes: Array<Record<string, unknown>>;
  edges: Array<Record<string, unknown>>;
};

export type BlankedField = {
  node_id: string;
  field_name: string;
};

export type TemplateCreateBody = {
  source_flow_id: string;
  name: string;
  description?: string | null;
  icon?: string | null;
  gradient?: string | null;
  blanked_fields?: BlankedField[];
  scope?: "platform" | "org";
  org_id?: string | null;
  category_ids?: string[];
};

export type TemplatePatchBody = {
  name?: string;
  description?: string | null;
  icon?: string | null;
  gradient?: string | null;
  /** null = leave tags unchanged; [] = clear all tags; id[] = full-replace */
  category_ids?: string[] | null;
};

export type TemplateUpdateBody = TemplateCreateBody;
