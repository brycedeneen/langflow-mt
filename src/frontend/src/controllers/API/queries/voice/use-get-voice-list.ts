import { useVoiceStore } from "@/stores/voiceStore";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { ElevenLabsVoiceIdsResponseSchema } from "@/schemas/app/internal/voice";
import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetVoiceList = (elevenlabsApiKey: string, options?: any) => {
  const { query } = UseRequestProcessor();
  const setVoices = useVoiceStore((state) => state.setVoices);
  const voices = useVoiceStore((state) => state.voices);

  const getVoiceListFn = async () => {
    if (voices.length > 0) {
      return voices;
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

    setVoices(voicesMapped);
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
  return queryResult;
};
