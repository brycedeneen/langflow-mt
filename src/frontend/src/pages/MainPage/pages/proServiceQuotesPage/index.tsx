import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useListQuotes } from "@/controllers/API/queries/pro-service-quotes";
import useAuthStore from "@/stores/authStore";
import type {
  ProServiceQuoteStatus,
  QuoteRead,
} from "@/types/pro-service-quote";
import { formatUSD } from "@/utils/formatMoney";

type StatusFilter = "open" | "in_progress" | "closed" | "all";

const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In progress" },
  { value: "closed", label: "Closed" },
  { value: "all", label: "All" },
];

function statusBadgeVariant(
  status: ProServiceQuoteStatus,
): "secondaryStatic" | "successStatic" | "emerald" {
  switch (status) {
    case "open":
      return "emerald";
    case "in_progress":
      return "successStatic";
    case "closed":
    default:
      return "secondaryStatic";
  }
}

function formatPriceRange(quote: QuoteRead): string {
  if (quote.rate_low_per_hour === null || quote.rate_high_per_hour === null) {
    return "—";
  }
  const minutesLow = quote.estimated_minutes_low;
  const minutesHigh = quote.estimated_minutes_high;
  const lowDollars = (Number(quote.rate_low_per_hour) * minutesLow) / 60;
  const highDollars = (Number(quote.rate_high_per_hour) * minutesHigh) / 60;
  if (Number.isNaN(lowDollars) || Number.isNaN(highDollars)) return "—";
  return `${formatUSD(lowDollars)} – ${formatUSD(highDollars)}`;
}

function formatSubmittedAt(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return "—";
  }
}

export const ProServiceQuotesPage = () => {
  const [status, setStatus] = useState<StatusFilter>("open");
  const navigate = useNavigate();

  const userData = useAuthStore((state) => state.userData);
  const isPlatformAdmin = userData?.is_platform_admin ?? false;
  const isSuperuser = userData?.is_superuser ?? false;
  const isAdmin = isSuperuser || isPlatformAdmin;

  const { data, isLoading, isError } = useListQuotes(
    status === "all" ? {} : { status },
  );

  const items: QuoteRead[] = useMemo(() => data?.items ?? [], [data]);

  const handleRowClick = (quoteId: string) => {
    navigate(`/pro-service-quotes/${quoteId}`);
  };

  const handleOpenFlow = (
    e: React.MouseEvent<HTMLAnchorElement>,
    flowId: string | null,
  ) => {
    // Prevent the row click from also firing — opening the flow should not
    // also navigate to the quote-detail page.
    e.stopPropagation();
    if (!flowId) e.preventDefault();
  };

  return (
    <div
      className="flex h-full w-full flex-col overflow-y-auto"
      data-testid="pro-service-quotes-page"
    >
      <div className="flex h-full w-full flex-col xl:container">
        <div className="flex flex-1 flex-col justify-start px-5 pt-10">
          <div
            className="flex items-center justify-between pb-4"
            data-testid="ps-quotes-header"
          >
            <div className="text-xl font-semibold">Pro-Service Quotes</div>
            <label className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Status:</span>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as StatusFilter)}
                className="flex h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-xs transition-colors focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring"
                data-testid="ps-quotes-status-filter"
              >
                {STATUS_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {isLoading ? (
            <div
              className="flex items-center justify-center py-12 text-muted-foreground"
              data-testid="ps-quotes-loading"
            >
              <ForwardedIconComponent
                name="Loader2"
                className="mr-2 h-4 w-4 animate-spin"
              />
              Loading quotes…
            </div>
          ) : isError ? (
            <div
              className="rounded border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
              data-testid="ps-quotes-error"
            >
              Failed to load quotes.
            </div>
          ) : items.length === 0 ? (
            <div
              className="rounded border border-dashed p-8 text-center text-muted-foreground"
              data-testid="ps-quotes-empty"
            >
              No quotes match this filter.
            </div>
          ) : (
            <Table data-testid="ps-quotes-table">
              <TableHeader>
                <TableRow>
                  {isAdmin ? (
                    <TableHead>Org name</TableHead>
                  ) : (
                    <TableHead>Flow</TableHead>
                  )}
                  <TableHead>Price range</TableHead>
                  <TableHead>Headline summary</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Submitted</TableHead>
                  <TableHead>Open flow</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((quote) => {
                  const flowId = quote.flow_id;
                  const flowLabel =
                    quote.flow_name ?? (flowId ? "Open flow" : "—");
                  return (
                    <TableRow
                      key={quote.id}
                      onClick={() => handleRowClick(quote.id)}
                      className="cursor-pointer"
                      data-testid={`ps-quote-row-${quote.id}`}
                    >
                      <TableCell>
                        {isAdmin
                          ? (quote.org_name ?? "—")
                          : (quote.flow_name ?? "—")}
                      </TableCell>
                      <TableCell>{formatPriceRange(quote)}</TableCell>
                      <TableCell className="max-w-[28rem] truncate">
                        {quote.headline_summary}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={statusBadgeVariant(quote.status)}
                          size="sq"
                        >
                          {quote.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {formatSubmittedAt(quote.submitted_at)}
                      </TableCell>
                      <TableCell>
                        {flowId ? (
                          <a
                            href={`/flow/${flowId}`}
                            onClick={(e) => handleOpenFlow(e, flowId)}
                            className="text-primary underline"
                            data-testid={`ps-quote-open-flow-${quote.id}`}
                          >
                            {flowLabel}
                          </a>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </div>
      </div>
    </div>
  );
};

export default ProServiceQuotesPage;
