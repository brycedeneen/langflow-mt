import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useGetOrganizations } from "@/controllers/API/queries/admin";
import type { OrgSummary } from "@/controllers/API/queries/admin";
import { Building2, Loader2, Search, X } from "lucide-react";
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
    <div className="flex h-full w-full flex-col gap-6">
      <div className="flex w-full items-start justify-between gap-6">
        <div className="flex flex-col">
          <h2
            className="flex items-center text-lg font-semibold tracking-tight"
            data-testid="settings_menu_header"
          >
            Org Admin
            <Building2
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">
            Manage platform organizations and their members.
          </p>
        </div>
        <div className="shrink-0">
          <Button
            variant="primary"
            onClick={() => navigate("/settings/organizations/new")}
          >
            New organization
          </Button>
        </div>
      </div>
      <div className="flex w-full justify-between">
        <div className="flex w-96 items-center gap-4">
          <Input
            placeholder="Search organizations"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search.length > 0 ? (
            <div className="cursor-pointer" onClick={() => setSearch("")}>
              <X className="w-6 text-foreground" />
            </div>
          ) : (
            <div>
              <Search className="w-6 text-foreground" />
            </div>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className="flex h-full w-full items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin" />
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
                  onClick={() => navigate(`/settings/organizations/${org.id}`)}
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
