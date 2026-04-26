import type { TagRead } from "@/types/tag";

export type MembershipOrg = {
  id: string;
  name: string;
  slug: string;
  is_personal: boolean;
};

export type MyMembership = {
  id: string;
  role: "owner"; // expand if the enum grows
  is_org_admin: boolean;
  organization: MembershipOrg;
};

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
  agent_summary: string | null;
  agent_usage_notes: string | null;
  tags?: TagRead[];
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
  agent_summary?: string | null;
  agent_usage_notes?: string | null;
};

export type TemplateUpdateBody = TemplateCreateBody;
