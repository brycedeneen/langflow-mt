import type { UseMutationResult } from "@tanstack/react-query";
import type {
  ResponseErrorDetailAPI,
  useMutationFunctionType,
} from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type InferredField = {
  name: string;
  type: "str" | "int" | "float" | "bool" | "list" | "dict" | "date" | "datetime";
  required: boolean;
};

export type JsonSchemaToFieldsResponse = { fields: InferredField[] };

export const usePostJsonSchemaToFields: useMutationFunctionType<
  undefined,
  Record<string, unknown>,
  JsonSchemaToFieldsResponse,
  ResponseErrorDetailAPI
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const postJsonSchemaToFieldsFn = async (
    schema: Record<string, unknown>,
  ): Promise<JsonSchemaToFieldsResponse> => {
    const response = await api.post<JsonSchemaToFieldsResponse>(
      getURL("VALIDATE", { 1: "jsonschema-to-fields" }),
      schema,
    );
    return response.data;
  };

  const mutation: UseMutationResult<
    JsonSchemaToFieldsResponse,
    ResponseErrorDetailAPI,
    Record<string, unknown>
  > = mutate(
    ["usePostJsonSchemaToFields"],
    postJsonSchemaToFieldsFn,
    options,
  );

  return mutation;
};
