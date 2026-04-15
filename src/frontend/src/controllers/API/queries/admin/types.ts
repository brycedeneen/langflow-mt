export interface OrgSummary {
  id: string;
  name: string;
  slug: string;
  member_count: number;
  created_at: string;
  updated_at: string;
}

export interface OrgListResponse {
  items: OrgSummary[];
  total: number;
}

export interface MemberRow {
  user_id: string;
  username: string;
  role: string;
  organization_id: string;
  organization_name: string;
}

export interface OrgDetail extends OrgSummary {
  members: MemberRow[];
}

export interface OrgDeleteResult {
  deleted: Record<string, number>;
}

export interface MemberAdd {
  user_id: string;
  role?: string;
}

export interface MembersResponse {
  items: MemberRow[];
}

export interface UserOrgRow {
  organization_id: string;
  organization_name: string;
  role: string;
}

export interface UserRow {
  id: string;
  username: string;
  is_platform_admin: boolean;
  memberships: UserOrgRow[];
}

export interface UserSearchResponse {
  items: UserRow[];
}

export interface OrgCreate {
  name: string;
  slug: string;
}
