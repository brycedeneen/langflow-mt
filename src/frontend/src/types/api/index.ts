import type {
  UseMutationOptions,
  UseMutationResult,
  UseQueryOptions,
  UseQueryResult,
} from "@tanstack/react-query";
import type { ChatInputType, ChatOutputType, UsageType } from "../chat";
import type { FlowType } from "../flow";
import type { ColumnField } from "../utils/functions";
//kind and class are just representative names to represent the actual structure of the object received by the API
export type APIDataType = { [key: string]: APIKindType };
export type APIObjectType = { [key: string]: APIKindType };
export type APIKindType = { [key: string]: APIClassType };
export type APITemplateType = {
  [key: string]: InputFieldType;
};

export type APICodeValidateType = {
  imports: { errors: Array<string> };
  function: { errors: Array<string> };
};

export type CustomFieldsType = {
  [key: string]: Array<string>;
};

export type CustomComponentRequest = {
  data: APIClassType;
  type: string;
};

export type ChangelogEntry = {
  version: number;
  changes: string;
  notes: string | null;
};

export type APIClassType = {
  base_classes?: Array<string>;
  description: string;
  template: APITemplateType;
  display_name: string;
  icon?: string;
  edited?: boolean;
  version?: number;
  changelog?: ChangelogEntry[];
  is_input?: boolean;
  is_output?: boolean;
  conditional_paths?: Array<string>;
  input_types?: Array<string>;
  output_types?: Array<string>;
  custom_fields?: CustomFieldsType;
  beta?: boolean;
  legacy?: boolean;
  assist_enabled?: boolean;
  replacement?: string[];
  documentation: string;
  error?: string;
  official?: boolean;
  outputs?: Array<OutputFieldType>;
  frozen?: boolean;
  lf_version?: string;
  flow?: FlowType;
  field_order?: string[];
  tool_mode?: boolean;
  type?: string;
  last_updated?: string;
  [key: string]:
    | Array<string>
    | string
    | APITemplateType
    | boolean
    | FlowType
    | CustomFieldsType
    | boolean
    | undefined
    | number
    | ChangelogEntry[]
    | Array<{ types: Array<string>; selected?: string }>;
};

export type ModelOptionType = {
  name: string;
  id?: string;
  icon?: string;
  provider?: string;
  metadata?: {
    is_disabled_provider?: boolean;
    [key: string]: unknown;
  };
};

export type InputFieldType = {
  type: string;
  required: boolean;
  placeholder?: string;
  list: boolean;
  show: boolean;
  readonly: boolean;
  password?: boolean;
  multiline?: boolean;
  // value can be any scalar/array/object the backend serialises for the field;
  // consumers narrow at the point of use.
  value?: unknown;
  dynamic?: boolean;
  proxy?: { id: string; field: string };
  input_types?: Array<string>;
  display_name?: string;
  name?: string;
  real_time_refresh?: boolean;
  refresh_button?: boolean;
  refresh_button_text?: string;
  combobox?: boolean;
  info?: string;
  // options is rendered by many widgets — strings, objects, arrays of objects.
  options?: unknown[];
  active_tab?: number;
  icon?: string;
  text?: string;
  temp_file?: boolean;
  separator?: string;
  /** TextFileSecretInput: accepted file extensions (e.g. ["pem", "crt"]) */
  file_types?: string[];
  // Additional optional properties accessed by consumers (snake_case from the
  // backend schema). Typed loosely because each widget interprets them differently.
  helper_text?: string;
  helper_text_metadata?: Record<string, unknown>;
  range_spec?: { min: number; max: number; step: number; step_type?: string };
  rangeSpec?: { min: number; max: number; step: number; step_type?: string };
  fields?: Record<string, unknown>;
  fileTypes?: Array<string>;
  file_path?: string | string[];
  // Backend may serialise as `{ columns: [...] }` or directly as the columns
  // array — the consumer probes `.columns` first then falls back to the array.
  table_schema?: { columns?: ColumnField[] } | ColumnField[];
  table_options?: TableOptionsTypeAPI;
  trigger_text?: string;
  trigger_icon?: string;
  table_icon?: string;
  min_label?: string;
  max_label?: string;
  min_label_icon?: string;
  max_label_icon?: string;
  slider_buttons?: boolean;
  slider_buttons_options?: { label: string; id: number }[];
  slider_input?: boolean;
  search_category?: string[];
  limit?: number;
  list_add_label?: string;
  external_options?: unknown;
  button_metadata?: { variant?: string; icon?: string };
  options_metadata?: unknown[];
  load_from_db?: boolean;
  advanced?: boolean;
  toggle?: boolean;
  toggle_value?: boolean;
  toggle_disable?: boolean;
  copy_field?: boolean;
  dialog_inputs?: Record<string, unknown>;
  archived_at?: string | null;
  helperText?: string;
  // Catch-all for any other backend-driven properties not enumerated above.
  // Use `unknown` so consumers must narrow before using.
  [key: string]: unknown;
};

export type OutputFieldProxyType = {
  id: string;
  name: string;
  nodeDisplayName: string;
};

export type OutputFieldType = {
  types: Array<string>;
  selected?: string;
  name: string;
  group_outputs?: boolean;
  method?: string;
  display_name: string;
  hidden?: boolean;
  proxy?: OutputFieldProxyType;
  allows_loop?: boolean;
  loop_types?: Array<string>;
  options?: { [key: string]: unknown };
};
export type errorsTypeAPI = {
  function: { errors: Array<string> };
  imports: { errors: Array<string> };
};
export type PromptTypeAPI = {
  input_variables: Array<string>;
  frontend_node: APIClassType;
};

export type BuildStatusTypeAPI = {
  built: boolean;
};

export type InitTypeAPI = {
  flowId: string;
};

export type UploadFileTypeAPI = {
  file_path: string;
  flowId: string;
};

export type ProfilePicturesTypeAPI = {
  files: string[];
};

export type LoginType = {
  grant_type?: string;
  username: string;
  password: string;
  scrope?: string;
  client_id?: string;
  client_secret?: string;
};

export type LoginAuthType = {
  access_token: string;
  refresh_token: string;
  token_type?: string;
};

export type changeUser = {
  username?: string;
  is_active?: boolean;
  is_superuser?: boolean;
  is_platform_admin?: boolean;
  password?: string;
  profile_image?: string;
  optins?: {
    github_starred?: boolean;
    discord_clicked?: boolean;
    dialog_dismissed?: boolean;
    mcp_dialog_dismissed?: boolean;
  };
};

export type resetPasswordType = {
  password?: string;
  profile_image?: string;
};

export type Users = {
  id: string;
  username: string;
  is_active: boolean;
  is_superuser: boolean;
  is_platform_admin: boolean;
  profile_image: string;
  create_at: Date;
  updated_at: Date;
  optins?: {
    github_starred?: boolean;
    discord_clicked?: boolean;
    dialog_dismissed?: boolean;
    mcp_dialog_dismissed?: boolean;
  };
};

export type Component = {
  name: string;
  description: string;
  // The flow/component graph payload — opaque at this boundary; consumers cast
  // to APIClassType / FlowType where appropriate.
  data: Record<string, unknown>;
  tags: [string];
};

export type VerticesOrderTypeAPI = {
  ids: Array<string>;
  vertices_to_run: Array<string>;
  run_id: string;
};

export type VertexBuildTypeAPI = {
  id: string;
  inactivated_vertices: Array<string> | null;
  next_vertices_ids: Array<string>;
  top_level_vertices: Array<string>;
  run_id?: string;
  valid: boolean;
  data: VertexDataTypeAPI;
  timestamp: string;
  // Backend serialises params as a string (PDF path, image URL, error
  // message, etc.) per VertexBuildTable in src/schemas/api/_generated.ts.
  // Inactive/synthetic builds may set this to null.
  params: string | null;
  messages: ChatOutputType[] | ChatInputType[];
  // Artifacts is a per-output-type payload — chat IO, repr objects, arrays —
  // opaque at this boundary; consumers narrow at point of use.
  artifacts: ChatOutputType | ChatInputType | Record<string, unknown> | unknown[] | null;
};

export type ErrorLogType = {
  errorMessage: string;
  stackTrace: string;
};

// Output/log message bodies are union-typed by the backend — string, error
// payload, array of records, etc. Consumers narrow on `type` at point of use.
export type LogMessageBody =
  | string
  | ErrorLogType
  | Record<string, unknown>
  | unknown[]
  | null;

export type OutputLogType = {
  message: LogMessageBody;
  type: string;
};
export type LogsLogType = {
  name: string;
  message: LogMessageBody;
  type: string;
};

// data is the object received by the API
// it has results, artifacts, timedelta, duration
export type VertexDataTypeAPI = {
  results: { [key: string]: string };
  outputs: { [key: string]: OutputLogType };
  logs: { [key: string]: LogsLogType };
  messages: ChatOutputType[] | ChatInputType[];
  inactive?: boolean;
  timedelta?: number;
  duration?: string;
  // Same union as VertexBuildTypeAPI.artifacts (see comment above) — but here
  // it's also conditionally narrowed via Array.isArray() at the consumer.
  artifacts?:
    | ChatOutputType
    | ChatInputType
    | Record<string, unknown>
    | unknown[]
    | null;
  message?: ChatOutputType | ChatInputType;
  token_usage?: UsageType | null;
};

export type CodeErrorDataTypeAPI = {
  error: string | undefined;
  traceback: string | undefined;
};

// the error above is inside this error.response.data.detail.error
// which comes from a request to the API
// to type the error we need to know the structure of the object

// error that has a response, that has a data, that has a detail, that has an error
export type ResponseErrorTypeAPI = {
  response: { data: { detail: CodeErrorDataTypeAPI } };
};
export type ResponseErrorDetailAPI = {
  response: { data: { detail: string } };
};
export type useQueryFunctionType<
  T = undefined,
  R = any,
  O = {},
> = T extends undefined
  ? (
      options?: Omit<UseQueryOptions, "queryFn" | "queryKey"> & O,
    ) => UseQueryResult<R>
  : (
      params: T,
      options?: Omit<UseQueryOptions, "queryFn" | "queryKey"> & O,
    ) => UseQueryResult<R>;

export type QueryFunctionType = (
  queryKey: UseQueryOptions["queryKey"],
  queryFn: UseQueryOptions["queryFn"],
  options?: Omit<UseQueryOptions, "queryKey" | "queryFn">,
) => UseQueryResult<any>;

export type MutationFunctionType = (
  mutationKey: UseMutationOptions["mutationKey"],
  mutationFn: UseMutationOptions<any, any, any>["mutationFn"],
  options?: Omit<UseMutationOptions<any, any>, "mutationFn" | "mutationKey">,
) => UseMutationResult<any, any, any, any>;

export type useMutationFunctionType<
  Params,
  Variables = any,
  Data = any,
  Error = any,
> = Params extends undefined
  ? (
      options?: Omit<
        UseMutationOptions<Data, Error>,
        "mutationFn" | "mutationKey"
      >,
    ) => UseMutationResult<Data, Error, Variables>
  : (
      params: Params,
      options?: Omit<
        UseMutationOptions<Data, Error>,
        "mutationFn" | "mutationKey"
      >,
    ) => UseMutationResult<Data, Error, Variables>;

export type FieldValidatorType =
  | "no_spaces"
  | "lowercase"
  | "uppercase"
  | "email"
  | "url"
  | "alphanumeric"
  | "numeric"
  | "alpha"
  | "phone"
  | "slug"
  | "username"
  | "password";

export type FieldParserType =
  | "mcp_name_case"
  | "snake_case"
  | "camel_case"
  | "pascal_case"
  | "kebab_case"
  | "lowercase"
  | "uppercase"
  | "no_blank"
  | "valid_csv"
  | "space_case"
  | "commands"
  | "sanitize_mcp_name";

export type TableOptionsTypeAPI = {
  block_add?: boolean;
  block_delete?: boolean;
  block_edit?: boolean;
  block_sort?: boolean;
  block_filter?: boolean;
  block_hide?: boolean | string[];
  block_select?: boolean;
  hide_options?: boolean;
  field_validators?: Array<
    FieldValidatorType | { [key: string]: FieldValidatorType }
  >;
  field_parsers?: Array<FieldParserType | { [key: string]: FieldParserType }>;
  description?: string;
};

export type TransactionLogsRow = {
  id: string;
  timestamp: string;
  vertex_id: string;
  target_id: string | null;
  inputs: Record<string, unknown> | null;
  outputs: Record<string, unknown> | null;
  status: string;
};

export type { ApiError } from "./error";
