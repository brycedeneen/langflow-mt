import { keepPreviousData } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type {
  TemplateMetadataRead,
  TemplateMetadataRow,
  TemplateMetadataWrite,
} from "@/types/metadata";

const baseURL = () => getURL("METADATA_TEMPLATES");

export function useListTemplateMetadata() {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<TemplateMetadataRow[]> => {
    const res = await api.get<TemplateMetadataRow[]>(baseURL());
    return res.data;
  };
  return query(["metadata", "templates", "list"], fn, {
    placeholderData: keepPreviousData,
  });
}

export function useUpsertTemplateMetadata() {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({
    flowId,
    body,
  }: {
    flowId: string;
    body: TemplateMetadataWrite;
  }): Promise<TemplateMetadataRead> => {
    const res = await api.put<TemplateMetadataRead>(
      `${baseURL()}/${flowId}`,
      body,
    );
    return res.data;
  };
  return mutate(["metadata", "templates", "upsert"], fn, {
    onSuccess: (data, variables, context) => {
      queryClient.invalidateQueries({
        queryKey: ["metadata", "templates", "list"],
      });
    },
  });
}

export function useDeleteTemplateMetadata() {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({ flowId }: { flowId: string }): Promise<void> => {
    await api.delete(`${baseURL()}/${flowId}`);
  };
  return mutate(["metadata", "templates", "delete"], fn, {
    onSuccess: (data, variables, context) => {
      queryClient.invalidateQueries({
        queryKey: ["metadata", "templates", "list"],
      });
    },
  });
}
