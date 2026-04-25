import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

// Permissive — voice-assistant WS messages have a wide shape; tighten when consumer reads stabilize.
export const VoiceAssistantMessageSchema = z.object({
  type: z.string().optional(),
}).passthrough();

registerSchema("stream.voiceAssistant", "permissive");
export type VoiceAssistantMessage = z.infer<typeof VoiceAssistantMessageSchema>;
