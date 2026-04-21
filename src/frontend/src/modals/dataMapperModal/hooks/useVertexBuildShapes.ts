// Reads the flow's vertex build pool from the flow store and extracts a
// `{alias, vertexId, fields}[]` map for the upstream vertices connected to
// this Data Mapper node.
//
// IMPORTANT: we DO NOT call `useGetBuildsQuery` here. That hook has a side
// effect (`setFlowPool`) that writes to the same Zustand store components in
// this tree subscribe to — leading to a render → refetch → render loop. The
// shared flowPool is kept up-to-date by the main flow view's own polling, so
// we only need to read it, not initiate queries ourselves.

import { useMemo } from "react";

import useFlowStore from "@/stores/flowStore";

import { FieldDef } from "@/modals/dataMapperModal/types";
import { inferSampleFields } from "@/modals/dataMapperModal/util/inferSampleFields";

export interface UpstreamShape {
  alias: string;
  vertexId: string;
  fields: FieldDef[] | null; // null = no recent build / not autodetectable
}

export interface UseVertexBuildShapesArgs {
  upstreams: { alias: string; vertexId: string }[];
}

export function useVertexBuildShapes({
  upstreams,
}: UseVertexBuildShapesArgs): { shapes: UpstreamShape[]; isPending: boolean } {
  const flowPool = useFlowStore((state) => state.flowPool);

  return useMemo(() => {
    const buildsByVertex = flowPool ?? {};

    const shapes: UpstreamShape[] = upstreams.map(({ alias, vertexId }) => {
      const builds = buildsByVertex[vertexId];
      if (!builds || builds.length === 0) {
        return { alias, vertexId, fields: null };
      }

      const latest = builds[builds.length - 1];
      const outputs = latest?.data?.outputs ?? {};
      const outputValues = Object.values(outputs);
      if (outputValues.length === 0) {
        return { alias, vertexId, fields: null };
      }

      const payload = (outputValues[0] as { message?: unknown })?.message;
      if (payload === undefined || payload === null) {
        return { alias, vertexId, fields: null };
      }

      const fields = inferSampleFields(payload);
      return {
        alias,
        vertexId,
        fields: fields.length > 0 ? fields : null,
      };
    });

    return { shapes, isPending: false };
  }, [flowPool, upstreams]);
}
