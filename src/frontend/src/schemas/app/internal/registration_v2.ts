import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

// Router-level include_in_schema=False in api/v2/registration.py

// POST /registration/ — response_model=RegisterResponse { email: str }
export const RegisterResponseSchema = z.looseObject({
  email: z.string(),
});

export type RegisterResponse = z.infer<typeof RegisterResponseSchema>;

// GET /registration/ — returns RegisterResponse dict or { message: str }; no response_model declared
// TODO: backend returns untyped dict — either { email, registered_at } or { message }
export const GetRegistrationResponseSchema = z.looseObject({
  email: z.string().optional(),
  registered_at: z.string().optional(),
  message: z.string().optional(),
});

export type GetRegistrationResponse = z.infer<typeof GetRegistrationResponseSchema>;

// POST /registration/
registerSchema("api.registration.create", "permissive");

// GET /registration/
registerSchema("api.registration.get", "permissive");
