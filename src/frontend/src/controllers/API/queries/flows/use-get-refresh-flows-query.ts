import type { UseQueryOptions } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { useEffect, useRef } from "react";
import { z } from "zod";
import buildQueryStringUrl from "@/controllers/utils/create-query-param-string";
import { validatedQueryFn } from "@/lib/validated-fetch";
import { FlowHeader, FlowRead, Page_FlowRead_ } from "@/schemas/api/_generated";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useTypesStore } from "@/stores/typesStore";
import type { APIClassType, useQueryFunctionType } from "@/types/api";
import type { FlowType, PaginatedFlowsType } from "@/types/flow";
import {
  extractSecretFieldsFromComponents,
  processFlows,
} from "@/utils/reactflowUtils";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

const FlowsResponseSchema = z.union([
  z.array(FlowRead),
  Page_FlowRead_,
  z.array(FlowHeader),
]);

interface GetFlowsParams {
  components_only?: boolean;
  get_all?: boolean;
  header_flows?: boolean;
  folder_id?: string;
  remove_example_flows?: boolean;
  page?: number;
  size?: number;
}

const addQueryParams = (url: string, params: GetFlowsParams): string => {
  return buildQueryStringUrl(url, params);
};

export const useGetRefreshFlowsQuery: useQueryFunctionType<
  GetFlowsParams,
  FlowType[] | PaginatedFlowsType
> = (params, options) => {
  const { query } = UseRequestProcessor();

  // Captures processed saved-components data computed inside the queryFn so the
  // effect below can sync it into useTypesStore without putting setState in
  // the queryFn body (render-loop hazard).
  const savedComponentsRef = useRef<{ [key: string]: APIClassType } | null>(
    null,
  );

  const getFlowsFn = async (
    params: GetFlowsParams,
  ): Promise<FlowType[] | PaginatedFlowsType> => {
    try {
      const url = addQueryParams(`${getURL("FLOWS")}/`, params);
      const dbDataFlows = await validatedQueryFn(
        "api.flows.read_flows_api_v1_flows__get",
        FlowsResponseSchema,
        async () => (await api.get<unknown>(url)).data,
      )();

      if (params.components_only) {
        return dbDataFlows as FlowType[];
      }

      const dbDataComponents = await validatedQueryFn(
        "api.flows.read_flows_api_v1_flows__get",
        FlowsResponseSchema,
        async () =>
          (
            await api.get<unknown>(
              addQueryParams(`${getURL("FLOWS")}/`, {
                components_only: true,
                get_all: true,
              }),
            )
          ).data,
      )();

      if (dbDataComponents) {
        const componentsArray = Array.isArray(dbDataComponents)
          ? dbDataComponents
          : (dbDataComponents as { items: FlowType[] }).items;
        const { data } = processFlows(componentsArray as FlowType[]);
        savedComponentsRef.current = data;
      } else {
        savedComponentsRef.current = null;
      }

      if (dbDataFlows) {
        const flows = (
          Array.isArray(dbDataFlows)
            ? dbDataFlows
            : (dbDataFlows as { items: FlowType[] }).items
        ) as FlowType[];
        return flows;
      }

      return [];
    } catch (e) {
      throw e;
    }
  };

  const queryResult = query(
    ["useGetRefreshFlowsQuery", params],
    () => getFlowsFn(params || {}),
    options as UseQueryOptions,
  );

  // Sync flows + saved components into stores outside the queryFn so this
  // hook does not subscribe to the stores it mutates. Setters and setState
  // are read via getState() to avoid subscribing.
  useEffect(() => {
    const data = queryResult.data;
    if (!data) return;
    const savedComponents = savedComponentsRef.current;
    if (savedComponents) {
      useTypesStore.setState((state) => ({
        data: { ...state.data, ["saved_components"]: savedComponents },
        ComponentFields: extractSecretFieldsFromComponents({
          ...state.data,
          ["saved_components"]: savedComponents,
        }),
      }));
    }
    // The queryFn always returns FlowType[] today (paginated branch is
    // unreachable in practice), but be defensive.
    if (Array.isArray(data)) {
      useFlowsManagerStore.getState().setFlows(data);
    }
  }, [queryResult.data]);

  useEffect(() => {
    const error = queryResult.error;
    if (!error) return;
    if (error instanceof AxiosError && error.status !== 403) {
      useAlertStore.getState().setErrorData({
        title: "Could not load flows from database",
      });
    }
  }, [queryResult.error]);

  return queryResult;
};
