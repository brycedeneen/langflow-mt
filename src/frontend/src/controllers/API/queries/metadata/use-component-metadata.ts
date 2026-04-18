import { keepPreviousData } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type {
  ComponentMetadataRead,
  ComponentMetadataRow,
  ComponentMetadataWrite,
} from "@/types/metadata";

const baseURL = () => getURL("METADATA_COMPONENTS");

export function useListComponentMetadata() {
  const { query } = UseRequestProcessor();
  const fn = async (): Promise<ComponentMetadataRow[]> => {
    const res = await api.get<ComponentMetadataRow[]>(baseURL());
    return res.data;
  };
  return query(["metadata", "components", "list"], fn, {
    placeholderData: keepPreviousData,
  });
}

export function useUpsertComponentMetadata() {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({
    componentName,
    body,
  }: {
    componentName: string;
    body: ComponentMetadataWrite;
  }): Promise<ComponentMetadataRead> => {
    const res = await api.put<ComponentMetadataRead>(
      `${baseURL()}/${encodeURIComponent(componentName)}`,
      body,
    );
    return res.data;
  };
  return mutate(["metadata", "components", "upsert"], fn, {
    onSuccess: (data, variables, context) => {
      queryClient.invalidateQueries({
        queryKey: ["metadata", "components", "list"],
      });
    },
  });
}

export function useDeleteComponentMetadata() {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async ({
    componentName,
  }: {
    componentName: string;
  }): Promise<void> => {
    await api.delete(`${baseURL()}/${encodeURIComponent(componentName)}`);
  };
  return mutate(["metadata", "components", "delete"], fn, {
    onSuccess: (data, variables, context) => {
      queryClient.invalidateQueries({
        queryKey: ["metadata", "components", "list"],
      });
    },
  });
}
