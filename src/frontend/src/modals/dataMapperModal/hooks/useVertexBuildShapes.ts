// Consumes the existing /monitor/builds query and extracts a `{alias: FieldDef[] | null}` map
// for the upstream vertex IDs connected to this Data Mapper node.

import { useMemo } from "react";
import { useGetBuildsQuery } from "@/controllers/API/queries/_builds/use-get-builds";

import { FieldDef } from "@/modals/dataMapperModal/types";
import { inferSampleFields } from "@/modals/dataMapperModal/util/inferSampleFields";

export interface UpstreamShape {
  alias: string;
  vertexId: string;
  fields: FieldDef[] | null; // null = no recent build / not autodetectable
}

export interface UseVertexBuildShapesArgs {
  flowId: string;
  upstreams: { alias: string; vertexId: string }[];
}

export function useVertexBuildShapes({
  flowId,
  upstreams,
}: UseVertexBuildShapesArgs): { shapes: UpstreamShape[]; isPending: boolean } {
  // useGetBuildsQuery returns UseQueryResult<AxiosResponse<{ vertex_builds: FlowPoolType }>>
  // FlowPoolType = { [vertexId: string]: Array<VertexBuildTypeAPI> }
  const { data, isPending } = useGetBuildsQuery({ flowId });

  // data is the AxiosResponse; the actual payload lives at data.data.vertex_builds
  const buildsByVertex = data?.data?.vertex_builds;

  return useMemo(() => {
    if (!buildsByVertex) {
      return {
        shapes: upstreams.map((u) => ({ ...u, fields: null })) as UpstreamShape[],
        isPending,
      };
    }

    const shapes: UpstreamShape[] = upstreams.map(({ alias, vertexId }) => {
      const builds = buildsByVertex[vertexId];
      if (!builds || builds.length === 0) return { alias, vertexId, fields: null };

      const latest = builds[builds.length - 1];

      // VertexBuildTypeAPI.data is VertexDataTypeAPI which has outputs, results, etc.
      // outputs is the primary source for field inference: { [outputName]: OutputLogType }
      // where OutputLogType = { message: any, type: string }.
      // Take the first output's message as the sample payload.
      const outputs = latest?.data?.outputs ?? {};
      const outputValues = Object.values(outputs);
      if (outputValues.length === 0) return { alias, vertexId, fields: null };

      // Each OutputLogType.message holds the actual data emitted by the node.
      const payload = (outputValues[0] as { message?: unknown })?.message;
      if (payload === undefined || payload === null) return { alias, vertexId, fields: null };

      const fields = inferSampleFields(payload);
      return { alias, vertexId, fields: fields.length > 0 ? fields : null };
    });

    return { shapes, isPending };
  }, [buildsByVertex, upstreams, isPending]);
}
