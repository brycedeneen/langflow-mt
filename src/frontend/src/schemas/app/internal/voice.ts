import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

// GET /voice/elevenlabs/voice_ids
// Returns a list of { voice_id, name } objects on success,
// or { error: string } on failure (backend returns raw dict with no response_model).
// TODO: backend returns untyped dict — success path is list, error path is { error: string }

export const ElevenLabsVoiceSchema = z
  .object({
    voice_id: z.string().optional(),
    name: z.string().optional().nullable(),
  })
  .passthrough();

export type ElevenLabsVoice = z.infer<typeof ElevenLabsVoiceSchema>;

// The endpoint can return either a list of voices or an error object
export const ElevenLabsVoiceIdsResponseSchema = z.union([
  z.array(ElevenLabsVoiceSchema),
  z.object({ error: z.string() }).passthrough(),
]);

export type ElevenLabsVoiceIdsResponse = z.infer<typeof ElevenLabsVoiceIdsResponseSchema>;

registerSchema("api.voice.elevenlabs_voice_ids", "permissive");
