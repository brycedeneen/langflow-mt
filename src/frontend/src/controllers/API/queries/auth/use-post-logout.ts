import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useLogout: useMutationFunctionType<undefined, void> = (
  options?,
) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const logout = useAuthStore((state) => state.logout);

  async function logoutUser(): Promise<any> {
    const res = await api.post(`${getURL("LOGOUT")}`);
    return res.data;
  }

  const cleanupLocalState = () => {
    logout();

    useFlowStore.getState().resetFlowState();
    useFlowsManagerStore.getState().resetStore();
    useFolderStore.getState().resetStore();

    // Clear all React Query cache to prevent data leakage between users
    queryClient.clear();
  };

  const mutation = mutate(["useLogout"], logoutUser, {
    onSuccess: cleanupLocalState,
    onError: (error) => {
      // A failed /logout POST still means the client is done with this session —
      // clear local state so stale-cookie users aren't stuck retrying in a loop.
      console.error(error);
      cleanupLocalState();
    },
    ...options,
    retry: false,
  });

  return mutation;
};
