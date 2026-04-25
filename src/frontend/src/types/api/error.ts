import type { AxiosError } from "axios";

/**
 * Standard error shape thrown by mutation/query hooks across the codebase.
 * The backend usually returns `{ detail: string | object }` on 4xx/5xx; we
 * narrow to the AxiosError envelope so call sites can read response.data.detail
 * with proper typing.
 */
export type ApiError<TBody = unknown> = AxiosError<{ detail?: unknown } & TBody>;
