import { getBaseUrl } from "@/customization/utils/urls";
import { BASE_URL_API_V2 } from "../../../constants/constants";

export const URLs = {
  TRANSACTIONS: `monitor/transactions`,
  TRACES: `monitor/traces`,
  API_KEY: `api_key`,
  FILES: `files`,
  FILE_MANAGEMENT: `files`,
  VERSION: `version`,
  MESSAGES: `monitor/messages`,
  BUILDS: `monitor/builds`,
  STORE: `store`,
  USERS: "users",
  LOGOUT: `logout`,
  LOGIN: `login`,
  SESSION: `session`,
  AUTOLOGIN: "auto_login",
  REFRESH: "refresh",
  BUILD: `build`,
  CUSTOM_COMPONENT: `custom_component`,
  FLOWS: `flows`,
  TEMPLATES: `templates`,
  FOLDERS: `projects`,
  PROJECTS: `projects`,
  VARIABLES: `variables`,
  VALIDATE: `validate`,
  CONFIG: `config`,
  STARTER_PROJECTS: `starter-projects`,
  SIDEBAR_CATEGORIES: `sidebar_categories`,
  ALL: `all`,
  VOICE: `voice`,
  PUBLIC_FLOW: `flows/public_flow`,
  MCP: `mcp/project`,
  MCP_SERVERS: `mcp/servers`,
  KNOWLEDGE_BASES: `knowledge_bases`,
  MODELS: `models`,
  MODEL_PROVIDERS: `models/providers`,
  RUN: `run`,
  RUN_SESSION: `run/session`,
  REGISTRATION: `registration`,
  CATEGORIES: `categories`,
  TAGS: `tags`,
  MEMBERSHIPS: `memberships`,
  ADMIN_ORGS: `admin/organizations`,
  ADMIN_TAGS: `admin/tags`,
  ADMIN_USERS: `admin/users`,
  ADMIN_AUDIT_LOGS: `admin/audit-logs`,
  ADMIN_AUDIT_LOG: `admin/audit-logs/`,
  METADATA_COMPONENTS: `admin/metadata/components`,
  METADATA_TEMPLATES: `admin/metadata/templates`,
  ORG_USAGE_KPI: `orgs`,
  ORG_USAGE_CHARTS: `orgs`,
  ORG_USAGE_FLOWS: `orgs`,
  FLOW_COST_SUMMARY: `flows`,
  FLOW_ESTIMATE_COST: `flows`,
  ADMIN_NOTIFICATIONS: `admin/notifications`,
  ADMIN_USAGE_THRESHOLDS: `admin/orgs`,
  ADMIN_USAGE_THRESHOLD: `admin/usage/thresholds`,
  ADMIN_ALERT_RULES: `admin/orgs`,
  ADMIN_ALERT_RULE: `admin/alert-rules`,
} as const;

// IMPORTANT: FOLDERS endpoint now points to 'projects' for backward compatibility

export function getURL(
  key: keyof typeof URLs,
  params: Record<string, unknown> = {},
  v2: boolean = false,
) {
  let url = URLs[key];
  for (const paramKey of Object.keys(params)) {
    url += `/${params[paramKey]}`;
  }
  return `${v2 ? BASE_URL_API_V2 : getBaseUrl()}${url}`;
}

export type URLsType = typeof URLs;
