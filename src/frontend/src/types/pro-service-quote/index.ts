// Pro-service quote types.
//
// Backend serialises ``Decimal`` values as JSON strings (e.g. ``"200.00"``);
// the frontend keeps them as ``string`` and parses to ``Number`` only at the
// point of display so we don't lose precision in transit.

export type ProServiceQuoteStatus = "open" | "in_progress" | "closed";

export type ComponentBreakdownItem = {
  type: string;
  minutes_low: number;
  minutes_high: number;
};

export type PreviewResponse = {
  minutes_low: number;
  minutes_high: number;
  rate_low_per_hour: string | null;
  rate_high_per_hour: string | null;
  cost_low: string | null;
  cost_high: string | null;
  headline_summary: string;
  narrative: string;
  conversation_summary: string | null;
  component_breakdown: ComponentBreakdownItem[];
};

export type QuoteSubmitRequest = {
  minutes_low: number;
  minutes_high: number;
  headline_summary: string;
  narrative: string;
  conversation_summary: string | null;
  org_notes: string | null;
};

export type QuoteRead = {
  id: string;
  org_id: string;
  org_name: string | null;
  flow_id: string | null;
  flow_name: string | null;
  requester_user_id: string;
  requester_email: string | null;
  status: ProServiceQuoteStatus;
  assigned_admin_user_id: string | null;
  estimated_minutes_low: number;
  estimated_minutes_high: number;
  rate_low_per_hour: string | null;
  rate_high_per_hour: string | null;
  headline_summary: string;
  narrative: string;
  conversation_summary: string | null;
  org_notes: string | null;
  admin_notes: string | null;
  created_at: string;
  submitted_at: string;
  in_progress_at: string | null;
  closed_at: string | null;
  closed_by_user_id: string | null;
};

export type QuoteListResponse = {
  items: QuoteRead[];
  total: number;
};

export type QuoteUpdatePayload = Partial<{
  org_notes: string;
  admin_notes: string;
  status: ProServiceQuoteStatus;
  assigned_admin_user_id: string;
}>;

export type ProServiceSettings = {
  default_hourly_rate_low: string | null;
  default_hourly_rate_high: string | null;
  webhook_url: string | null;
  has_webhook_secret: boolean;
};

export type ProServiceSettingsWrite = Partial<{
  default_hourly_rate_low: string;
  default_hourly_rate_high: string;
  webhook_url: string;
  webhook_secret: string;
}>;

export type ProServiceWebhookTestResult = {
  status: "ok" | "failed";
  status_code?: number;
  detail?: string;
};
