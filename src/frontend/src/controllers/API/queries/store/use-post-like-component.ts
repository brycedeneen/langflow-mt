import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostLikeComponent {
  componentId: string;
}

export const usePostLikeComponent: useMutationFunctionType<
  undefined,
  IPostLikeComponent
> = (options) => {
  const { mutate } = UseRequestProcessor();

  const postLikeComponent = async (
    payload: IPostLikeComponent,
  ): Promise<unknown> => {
    const { componentId } = payload;
    return await api.post<unknown>(`${getURL("STORE")}/users/likes/${componentId}`);
  };

  const mutation = mutate(["usePostLikeComponent"], postLikeComponent, options);

  return mutation;
};
