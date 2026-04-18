export type TemplateMetadataRead = {
  agent_usage_notes: string | null;
  agent_summary: string | null;
  updated_by: string;
  updated_at: string;
};

export type TemplateMetadataRow = {
  flow_id: string;
  flow_name: string;
  flow_description: string | null;
  is_starter: boolean;
  metadata: TemplateMetadataRead | null;
};

export type TemplateMetadataWrite = {
  agent_usage_notes: string | null;
  agent_summary: string | null;
};

export type ComponentMetadataRead = TemplateMetadataRead;

export type ComponentMetadataRow = {
  component_name: string;
  display_name: string | null;
  category: string | null;
  icon: string | null;
  is_orphan: boolean;
  metadata: ComponentMetadataRead | null;
};

export type ComponentMetadataWrite = {
  agent_usage_notes: string | null;
  agent_summary: string | null;
};
