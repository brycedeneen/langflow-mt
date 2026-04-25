import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

// Mirrors UserRead from langflow/services/database/models/user/model.py
export const UserReadSchema = z.looseObject({
  id: z.string().optional(),
  username: z.string(),
  profile_image: z.string().optional().nullable(),
  store_api_key: z.string().optional().nullable(),
  is_active: z.boolean(),
  is_superuser: z.boolean(),
  is_platform_admin: z.boolean(),
  create_at: z.string().optional(),
  updated_at: z.string().optional(),
  last_login_at: z.string().optional().nullable(),
  optins: z.record(z.string(), z.unknown()).optional().nullable(),
});

export type UserRead = z.infer<typeof UserReadSchema>;

// POST /login — response_model=Token
// Token from langflow/api/v1/schemas/__init__.py
export const TokenResponseSchema = z.looseObject({
  access_token: z.string(),
  refresh_token: z.string().optional(),
  token_type: z.string(),
});

export type TokenResponse = z.infer<typeof TokenResponseSchema>;

// POST /refresh — no explicit response_model; returns same token dict
export const RefreshResponseSchema = TokenResponseSchema;
export type RefreshResponse = z.infer<typeof RefreshResponseSchema>;

// GET /session — response_model=SessionResponse (defined in login.py)
export const SessionResponseSchema = z.looseObject({
  authenticated: z.boolean(),
  user: UserReadSchema.optional().nullable(),
  store_api_key: z.string().optional().nullable(),
});

export type SessionResponse = z.infer<typeof SessionResponseSchema>;

// POST /logout — returns {"message": "Logout successful"}
export const LogoutResponseSchema = z.looseObject({
  message: z.string(),
});

export type LogoutResponse = z.infer<typeof LogoutResponseSchema>;

// Login uses OAuth2PasswordRequestForm (form-encoded: username + password)
// No separate LoginRequestSchema needed — sent as application/x-www-form-urlencoded

registerSchema("api.auth.login", "permissive");
registerSchema("api.auth.refresh", "permissive");
registerSchema("api.auth.getSession", "permissive");
registerSchema("api.auth.logout", "permissive");
