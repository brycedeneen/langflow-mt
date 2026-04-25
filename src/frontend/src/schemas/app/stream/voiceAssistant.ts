import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

// Permissive — voice-assistant WS messages have a wide shape; tighten when consumer reads stabilize.
export const VoiceAssistantMessageSchema = z.looseObject({
  type: z.string().optional(),
});

registerSchema("stream.voiceAssistant", "permissive");
export type VoiceAssistantMessage = z.infer<typeof VoiceAssistantMessageSchema>;
