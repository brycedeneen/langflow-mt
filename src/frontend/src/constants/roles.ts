export type MembershipRole = "owner" | "admin" | "member" | "operator" | "viewer";

export const ROLE_ORDER: Record<MembershipRole, number> = {
  owner: 5,
  admin: 4,
  member: 3,
  operator: 2,
  viewer: 1,
};

export const ROLE_METADATA: Record<MembershipRole, {
  label: string;
  description: string;
  color: string;
}> = {
  owner: {
    label: "Owner",
    description: "Full access. Manages members and org settings. Can delete the organization.",
    color: "text-purple-700 bg-purple-50",
  },
  admin: {
    label: "Admin",
    description: "Manages members and org settings. Cannot delete the organization or create other Admins or Owners.",
    color: "text-blue-700 bg-blue-50",
  },
  member: {
    label: "Member",
    description: "Creates, edits, and runs flows. Cannot manage members or org settings.",
    color: "text-emerald-700 bg-emerald-50",
  },
  operator: {
    label: "Operator",
    description: "Runs flows and views results. Cannot edit flows or manage the organization.",
    color: "text-amber-700 bg-amber-50",
  },
  viewer: {
    label: "Viewer",
    description: "Views flows and their configuration. Cannot run or edit anything.",
    color: "text-slate-700 bg-slate-100",
  },
};

export function canAssignRole(args: {
  caller: MembershipRole | "platform_admin";
  current: MembershipRole;
  next: MembershipRole;
}): boolean {
  const { caller, current, next } = args;
  if (caller === "platform_admin" || caller === "owner") return true;
  if (caller === "admin") {
    const below: MembershipRole[] = ["member", "operator", "viewer"];
    return below.includes(current) && below.includes(next);
  }
  return false;
}
