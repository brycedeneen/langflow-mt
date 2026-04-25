import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

// Chat message stream events for LLM token streaming.
// Consumer (use-streaming-message.ts / chat-message.tsx) reads:
//   parsedData.chunk — string token appended to the message buffer
// The stream is closed via a custom "close" SSE event (not via this schema).

export const ChatMessageChunkSchema = z.looseObject({
  chunk: z.string().optional(),
  done: z.boolean().optional(),
});

registerSchema("stream.chatMessages", "permissive");

export type ChatMessageChunk = z.infer<typeof ChatMessageChunkSchema>;
