import { useContext } from "react";
import type { ReactNode } from "react";
import { AuthContext } from "@/contexts/authContext";
import useAuthStore from "@/stores/authStore";
import { CustomNavigate } from "@/customization/components/custom-navigate";
import { LoadingPage } from "@/pages/LoadingPage";

type Props = { children: ReactNode };

export const ProtectedSuperuserRoute = ({ children }: Props) => {
  const { userData } = useContext(AuthContext);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  if (!isAuthenticated) {
    return <LoadingPage />;
  }
  if (!userData?.is_superuser) {
    return <CustomNavigate to="/" replace />;
  }
  return <>{children}</>;
};
