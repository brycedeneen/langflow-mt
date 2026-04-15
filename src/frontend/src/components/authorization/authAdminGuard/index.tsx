import { useContext } from "react";
import { AuthContext } from "@/contexts/authContext";
import { CustomNavigate } from "@/customization/components/custom-navigate";
import { LoadingPage } from "@/pages/LoadingPage";
import useAuthStore from "@/stores/authStore";

export const ProtectedAdminRoute = ({ children }) => {
  const { userData } = useContext(AuthContext);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const isAdmin = useAuthStore((state) => state.isAdmin);

  const isPlatformAdmin = userData?.is_platform_admin === true;

  if (!isAuthenticated) {
    return <LoadingPage />;
  } else if ((userData && !isAdmin && !isPlatformAdmin) || autoLogin) {
    return <CustomNavigate to="/" replace />;
  } else {
    return children;
  }
};
