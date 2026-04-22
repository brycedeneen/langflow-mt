import { useState } from "react";
import { useNavigate } from "react-router-dom";
import RoleBadge from "@/components/common/roleBadge";
import { useRemoveMember } from "@/controllers/API/queries/admin";
import type { MemberRow } from "@/controllers/API/queries/admin";
import type { MembershipRole } from "@/constants/roles";
import IconComponent from "../../../components/common/genericIconComponent";
import { Button } from "../../../components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../../components/ui/table";
import AddMemberDialog from "./AddMemberDialog";

interface OrganizationMembersTabProps {
  orgId: string;
  members: MemberRow[];
}

export default function OrganizationMembersTab({
  orgId,
  members,
}: OrganizationMembersTabProps) {
  const navigate = useNavigate();
  const [addDialogOpen, setAddDialogOpen] = useState(false);

  const { mutate: removeMember, isPending: isRemoving } = useRemoveMember();

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end">
        <Button variant="primary" onClick={() => setAddDialogOpen(true)}>
          Add member
        </Button>
      </div>

      {members.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No members yet. Add one above.
        </p>
      ) : (
        <div className="overflow-x-hidden overflow-y-scroll rounded-md border bg-background custom-scroll">
          <Table className="table-fixed">
            <TableHeader className="bg-muted">
              <TableRow>
                <TableHead className="h-10">Username</TableHead>
                <TableHead className="h-10">Role</TableHead>
                <TableHead className="h-10 w-24">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.map((member) => (
                <TableRow key={member.user_id}>
                  <TableCell className="truncate py-2 font-medium">
                    <button
                      className="cursor-pointer text-left hover:underline"
                      onClick={() =>
                        navigate(
                          `/settings/organizations/${orgId}/members/${member.user_id}`,
                        )
                      }
                    >
                      {member.username}
                    </button>
                  </TableCell>
                  <TableCell className="truncate py-2">
                    <RoleBadge role={member.role as MembershipRole} />
                  </TableCell>
                  <TableCell className="py-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={isRemoving}
                      className="text-destructive hover:text-destructive"
                      onClick={() =>
                        removeMember({ orgId, userId: member.user_id })
                      }
                    >
                      Remove
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <AddMemberDialog
        orgId={orgId}
        open={addDialogOpen}
        onClose={() => setAddDialogOpen(false)}
      />
    </div>
  );
}
