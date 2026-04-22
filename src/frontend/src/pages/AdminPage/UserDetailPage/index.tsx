import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useGetUser } from "@/controllers/API/queries/admin/use-get-user";
import CustomLoader from "@/customization/components/custom-loader";
import AccountTab from "./AccountTab";
import MembershipsTab from "./MembershipsTab";

export default function UserDetailPage() {
  const { userId = "" } = useParams();
  const navigate = useNavigate();
  const { data: user, isPending, error } = useGetUser({ userId });
  const [tab, setTab] = useState<"account" | "memberships">("account");

  if (isPending) return <CustomLoader remSize={12} />;
  if (error || !user) return <div className="p-6">User not found.</div>;

  return (
    <div className="flex h-full w-full flex-col">
      {/* Breadcrumb */}
      <div className="border-b px-6 py-3 text-sm text-muted-foreground">
        <button
          className="hover:underline"
          onClick={() => navigate("/settings/users")}
        >
          Users
        </button>
        <span className="mx-2">/</span>
        <span>{user.username}</span>
      </div>

      {/* Identity header */}
      <div className="flex items-center gap-4 border-b bg-muted/30 p-6">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary text-lg font-semibold text-primary-foreground">
          {user.username.slice(0, 2).toUpperCase()}
        </div>
        <div className="flex-1">
          <div className="text-xl font-semibold">{user.username}</div>
          <div className="font-mono text-sm text-muted-foreground">
            {user.id}
          </div>
        </div>
        <div className="flex gap-2">
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              user.is_active
                ? "bg-green-100 text-green-700"
                : "bg-red-100 text-red-700"
            }`}
            data-testid="status-pill"
          >
            ● {user.is_active ? "Active" : "Inactive"}
          </span>
          {user.is_platform_admin && (
            <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
              Platform Admin
            </span>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-0 border-b px-6">
        <TabButton
          active={tab === "account"}
          onClick={() => setTab("account")}
        >
          Account
        </TabButton>
        <TabButton
          active={tab === "memberships"}
          onClick={() => setTab("memberships")}
        >
          Memberships · {user.memberships.length}
        </TabButton>
      </div>

      <div className="flex-1 overflow-auto p-6">
        {tab === "account" ? (
          <AccountTab user={user} />
        ) : (
          <MembershipsTab user={user} />
        )}
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`border-b-2 px-4 py-3 font-medium ${
        active
          ? "border-primary text-foreground"
          : "border-transparent text-muted-foreground"
      }`}
    >
      {children}
    </button>
  );
}
