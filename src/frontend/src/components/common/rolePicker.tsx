import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  canAssignRole,
  type MembershipRole,
  ROLE_METADATA,
} from "@/constants/roles";

interface Props {
  caller: MembershipRole | "platform_admin";
  current: MembershipRole;
  onSelect: (next: MembershipRole) => void;
  disabled?: boolean;
}

const ALL_ROLES: MembershipRole[] = [
  "owner",
  "admin",
  "member",
  "operator",
  "viewer",
];

export default function RolePicker({
  caller,
  current,
  onSelect,
  disabled,
}: Props) {
  const canPotentiallyAssign =
    caller === "platform_admin" || caller === "owner" || caller === "admin";
  const readOnly = Boolean(disabled) || !canPotentiallyAssign;

  return (
    <Select
      value={current}
      onValueChange={(v) => onSelect(v as MembershipRole)}
      disabled={readOnly}
    >
      <SelectTrigger data-testid="role-picker-trigger" disabled={readOnly}>
        <SelectValue>{ROLE_METADATA[current].label}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        {ALL_ROLES.map((role) => {
          const allowed = canAssignRole({ caller, current, next: role });
          return (
            <SelectItem
              key={role}
              value={role}
              disabled={!allowed}
              aria-disabled={!allowed}
              data-testid={`role-option-${role}`}
            >
              <div className="flex flex-col">
                <span className="font-medium">{ROLE_METADATA[role].label}</span>
                <span className="text-xs text-muted-foreground">
                  {ROLE_METADATA[role].description}
                </span>
              </div>
            </SelectItem>
          );
        })}
      </SelectContent>
    </Select>
  );
}
