import type { z } from "zod";
import { getMode } from "./schema-registry";
import { ValidationError, reportParseFailure } from "./schema-errors";

export function validatedQueryFn<TSchema extends z.ZodType>(
  id: string,
  schema: TSchema,
  call: () => Promise<unknown>,
): () => Promise<z.infer<TSchema>> {
  return async () => {
    const raw = await call();
    const result = schema.safeParse(raw);
    if (result.success) return result.data;
    const mode = getMode(id);
    reportParseFailure({ id, mode, error: result.error, raw, boundary: "http" });
    if (mode === "strict") throw new ValidationError(id, result.error, "http");
    return raw as z.infer<TSchema>;
  };
}

export function validatedMutationFn<TReqSchema extends z.ZodType, TResSchema extends z.ZodType>(
  id: string,
  reqSchema: TReqSchema,
  resSchema: TResSchema,
  call: (body: z.infer<TReqSchema>) => Promise<unknown>,
): (body: z.infer<TReqSchema>) => Promise<z.infer<TResSchema>> {
  return async (body) => {
    const mode = getMode(id);

    // Validate request body before firing.
    const reqResult = reqSchema.safeParse(body);
    if (!reqResult.success) {
      reportParseFailure({ id: `${id}.request`, mode, error: reqResult.error, raw: body, boundary: "http" });
      if (mode === "strict") throw new ValidationError(`${id}.request`, reqResult.error, "http");
    }

    const raw = await call(body);

    const resResult = resSchema.safeParse(raw);
    if (resResult.success) return resResult.data;
    reportParseFailure({ id: `${id}.response`, mode, error: resResult.error, raw, boundary: "http" });
    if (mode === "strict") throw new ValidationError(`${id}.response`, resResult.error, "http");
    return raw as z.infer<TResSchema>;
  };
}
