import useAuthStore from "@/stores/authStore";

export function useIsPlatformAdmin(): boolean {
  return useAuthStore((s) => Boolean(s.userData?.is_platform_admin));
}
