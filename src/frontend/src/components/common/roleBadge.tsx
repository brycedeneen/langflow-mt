import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { type MembershipRole, ROLE_METADATA } from "@/constants/roles";

interface Props {
  role: MembershipRole;
  className?: string;
}

export default function RoleBadge({ role, className = "" }: Props) {
  const meta = ROLE_METADATA[role];
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${meta.color} ${className}`}
            data-testid={`role-badge-${role}`}
          >
            {meta.label}
          </span>
        </TooltipTrigger>
        <TooltipContent>{meta.description}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
