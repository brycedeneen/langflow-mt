import { test } from "node:test";
import assert from "node:assert/strict";
import { rewriteV3ToV4 } from "../zod4-postprocessor.mjs";

test("rewrites trailing .passthrough() into z.looseObject wrap (single-line)", () => {
  const input = `export const SendMessageRequest = z.object({ content: z.string() }).passthrough();`;
  const output = rewriteV3ToV4(input);
  assert.equal(output, `export const SendMessageRequest = z.looseObject({ content: z.string() });`);
});

test("rewrites trailing .passthrough() into z.looseObject wrap (multi-line block)", () => {
  const input = [
    `export const Foo = z`,
    `  .object({`,
    `    a: z.string(),`,
    `    b: z.number(),`,
    `  })`,
    `  .passthrough();`,
  ].join("\n");
  const output = rewriteV3ToV4(input);
  assert.equal(
    output,
    [
      `export const Foo = z.looseObject({`,
      `    a: z.string(),`,
      `    b: z.number(),`,
      `  });`,
    ].join("\n"),
  );
});

test("rewrites inline .object({}).partial().passthrough() into z.looseObject({}).partial()", () => {
  const input = `template: z.object({}).partial().passthrough().optional(),`;
  const output = rewriteV3ToV4(input);
  assert.equal(output, `template: z.looseObject({}).partial().optional(),`);
});

test("rewrites trailing .strict() into z.strictObject wrap", () => {
  const input = `export const Foo = z.object({ a: z.string() }).strict();`;
  const output = rewriteV3ToV4(input);
  assert.equal(output, `export const Foo = z.strictObject({ a: z.string() });`);
});

test("rewrites single-arg z.record(V) to z.record(z.string(), V)", () => {
  const input = `vertex_builds: z.record(z.array(VertexBuildTable))`;
  const output = rewriteV3ToV4(input);
  assert.equal(output, `vertex_builds: z.record(z.string(), z.array(VertexBuildTable))`);
});

test("leaves two-arg z.record(K, V) untouched", () => {
  const input = `env: z.record(z.string(), z.string())`;
  const output = rewriteV3ToV4(input);
  assert.equal(output, input);
});

test("rewrites z.nativeEnum(X) to z.enum(X)", () => {
  const input = `kind: z.nativeEnum(NodeKind)`;
  const output = rewriteV3ToV4(input);
  assert.equal(output, `kind: z.enum(NodeKind)`);
});

test("does not touch passthrough mentions inside string literals", () => {
  const input = `description: z.literal("must use .passthrough()")`;
  const output = rewriteV3ToV4(input);
  assert.equal(output, input);
});

test("is idempotent on already-v4 source", () => {
  const input = `export const Foo = z.looseObject({ a: z.string() });`;
  const output = rewriteV3ToV4(input);
  assert.equal(output, input);
});
