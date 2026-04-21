import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { TEMPLATES_QUERY_KEY } from "./use-list-templates";

export function useHardDeleteTemplate() {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({ templateId }: { templateId: string }): Promise<void> => {
    await api.delete(`${getURL("TEMPLATES")}/${templateId}`);
  };
  return mutate([...TEMPLATES_QUERY_KEY, "hardDelete"], fn, {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TEMPLATES_QUERY_KEY });
    },
    // On 409, the caller inspects err.response?.status === 409
    // and err.response?.data?.detail?.referencing_flow_ids to surface the
    // "N flow(s) still reference this template" message.
  });
}
