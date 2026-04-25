import { useEffect } from "react";
import { useVoiceStore } from "@/stores/voiceStore";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { ElevenLabsVoiceIdsResponseSchema } from "@/schemas/app/internal/voice";
import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetVoiceList = (elevenlabsApiKey: string, options?: any) => {
  const { query } = UseRequestProcessor();

  const getVoiceListFn = async () => {
    const cachedVoices = useVoiceStore.getState().voices;
    if (cachedVoices.length > 0) {
      return cachedVoices;
    }
    if (!elevenlabsApiKey) {
      return [];
    }

    const data = await validatedQueryFn(
      "api.voice.elevenlabs_voice_ids",
      ElevenLabsVoiceIdsResponseSchema,
      async () =>
        (await api.get<unknown>(`${getURL("VOICE")}/elevenlabs/voice_ids`))
          .data,
    )();

    // If the response is an error object rather than a list, return empty
    if (!Array.isArray(data)) {
      return [];
    }

    // Map to { name, value, voice_id } so:
    //   - VoiceSelect and allVoices consumers read .value (required by SelectItem)
    //   - setVoices receives objects with the correct .voice_id field (store type)
    const voicesMapped = data.map((voice) => ({
      name: voice.name ?? "",
      value: voice.voice_id ?? "",
      voice_id: voice.voice_id ?? "",
    }));

    return voicesMapped;
  };

  const defaultOptions = {
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    staleTime: 1000 * 60 * 5,
    ...options,
  };

  const queryResult = query(
    ["useGetVoiceList", elevenlabsApiKey],
    getVoiceListFn,
    defaultOptions,
  );

  // Sync voices into the voice store outside the queryFn so this hook does
  // not subscribe to the store it mutates. Setter is read via getState().
  useEffect(() => {
    const data = queryResult.data;
    if (!data || data.length === 0) return;
    // Avoid redundant set if the store already has the same identity.
    if (useVoiceStore.getState().voices === data) return;
    useVoiceStore.getState().setVoices(data);
  }, [queryResult.data]);

  return queryResult;
};
