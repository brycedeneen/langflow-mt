import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useGetOrganizations } from "@/controllers/API/queries/admin";
import type { OrgSummary } from "@/controllers/API/queries/admin";
import IconComponent from "../../../components/common/genericIconComponent";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../../components/ui/table";

export default function OrganizationsListPage() {
  const [search, setSearch] = useState("");
  const navigate = useNavigate();

  const { data, isLoading } = useGetOrganizations({ q: search || undefined });

  const orgs: OrgSummary[] = data?.items ?? [];

  return (
    <div className="admin-page-panel flex h-full flex-col pb-8">
      <div className="main-page-nav-arrangement">
        <span className="main-page-nav-title">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <IconComponent name="ChevronLeft" className="w-5" />
          </Button>
          <IconComponent name="Building2" className="w-6" />
          Organizations
        </span>
      </div>
      <span className="admin-page-description-text">
        Manage platform organizations and their members.
      </span>
      <div className="flex w-full justify-between">
        <div className="flex w-96 items-center gap-4">
          <Input
            placeholder="Search organizations"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search.length > 0 ? (
            <div className="cursor-pointer" onClick={() => setSearch("")}>
              <IconComponent name="X" className="w-6 text-foreground" />
            </div>
          ) : (
            <div>
              <IconComponent name="Search" className="w-6 text-foreground" />
            </div>
          )}
        </div>
        <div>
          <Button
            variant="primary"
            onClick={() => navigate("/admin/organizations/new")}
          >
            New organization
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex h-full w-full items-center justify-center">
          <IconComponent name="Loader2" className="h-8 w-8 animate-spin" />
        </div>
      ) : orgs.length === 0 ? (
        <div className="m-4 flex items-center justify-between text-sm">
          No organizations found.
        </div>
      ) : (
        <div className="my-4 flex-1 overflow-x-hidden overflow-y-scroll rounded-md border bg-background custom-scroll">
          <Table className="table-fixed outline-1">
            <TableHeader className="table-fixed bg-muted outline-1">
              <TableRow>
                <TableHead className="h-10">Name</TableHead>
                <TableHead className="h-10">Slug</TableHead>
                <TableHead className="h-10">Members</TableHead>
                <TableHead className="h-10">Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className="border-b">
              {orgs.map((org) => (
                <TableRow
                  key={org.id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => navigate(`/admin/organizations/${org.id}`)}
                >
                  <TableCell className="truncate py-2 font-medium">
                    {org.name}
                  </TableCell>
                  <TableCell className="truncate py-2">{org.slug}</TableCell>
                  <TableCell className="truncate py-2">
                    {org.member_count}
                  </TableCell>
                  <TableCell className="truncate py-2">
                    {new Date(org.created_at).toISOString().split("T")[0]}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
