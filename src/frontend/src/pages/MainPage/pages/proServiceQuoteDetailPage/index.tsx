import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ExternalLink, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  useGetQuote,
  useUpdateQuote,
} from "@/controllers/API/queries/pro-service-quotes";
import useAuthStore from "@/stores/authStore";
import type {
  ProServiceQuoteStatus,
  QuoteRead,
  QuoteUpdatePayload,
} from "@/types/pro-service-quote";
import { formatUSD } from "@/utils/formatMoney";

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

function renderMinutesRange(low: number, high: number): string {
  if (high < 60) return `${low} min – ${high} min`;
  return `${(low / 60).toFixed(1)} hr – ${(high / 60).toFixed(1)} hr`;
}

function renderDollarRange(quote: QuoteRead): string | null {
  if (quote.rate_low_per_hour === null || quote.rate_high_per_hour === null) {
    return null;
  }
  const low = (Number(quote.rate_low_per_hour) * quote.estimated_minutes_low) / 60;
  const high =
    (Number(quote.rate_high_per_hour) * quote.estimated_minutes_high) / 60;
  if (Number.isNaN(low) || Number.isNaN(high)) return null;
  return `${formatUSD(low)} – ${formatUSD(high)}`;
}

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return "—";
  }
}

export const ProServiceQuoteDetailPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const userData = useAuthStore((state) => state.userData);

  const isPlatformAdmin = userData?.is_platform_admin ?? false;
  const isSuperuser = userData?.is_superuser ?? false;
  const isAdmin = isSuperuser || isPlatformAdmin;

  const { data: quote, isLoading, isError } = useGetQuote(id ?? null);
  const update = useUpdateQuote();

  const [orgNotes, setOrgNotes] = useState("");
  const [adminNotes, setAdminNotes] = useState("");

  useEffect(() => {
    if (quote) {
      setOrgNotes(quote.org_notes ?? "");
      setAdminNotes(quote.admin_notes ?? "");
    }
  }, [quote?.id]);

  if (isLoading) {
    return (
      <div
        className="flex h-full items-center justify-center text-muted-foreground"
        data-testid="ps-quote-detail-loading"
      >
        <Loader2
          className="mr-2 h-4 w-4 animate-spin"
        />
        Loading quote…
      </div>
    );
  }

  if (isError || !quote) {
    return (
      <div
        className="m-6 rounded border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
        data-testid="ps-quote-detail-error"
      >
        Failed to load this quote.
      </div>
    );
  }

  const isRequester =
    !!userData?.id && userData.id === quote.requester_user_id;
  const dollarRange = renderDollarRange(quote);

  const submit = (body: QuoteUpdatePayload) => {
    if (!id) return;
    update.mutate({ quoteId: id, body });
  };

  return (
    <div
      className="flex h-full w-full flex-col overflow-y-auto"
      data-testid="pro-service-quote-detail-page"
    >
      <div className="flex h-full w-full flex-col xl:container">
        <div className="flex flex-1 flex-col px-5 pt-10">
          <button
            type="button"
            onClick={() => navigate("/pro-service-quotes")}
            className="mb-4 flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-primary"
            data-testid="ps-quote-detail-back"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to list
          </button>

          <div className="grid gap-6 lg:grid-cols-2">
            {/* Left column — read-only */}
            <div className="space-y-4">
              <div>
                <div className="mb-1 text-xs uppercase tracking-wide text-muted-foreground">
                  Headline
                </div>
                <div className="text-lg font-semibold" data-testid="ps-detail-headline">
                  {quote.headline_summary}
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Badge variant={statusBadgeVariant(quote.status)} size="sq">
                  {quote.status}
                </Badge>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">
                    Hours range
                  </div>
                  <div className="text-base font-medium" data-testid="ps-detail-hours">
                    {renderMinutesRange(
                      quote.estimated_minutes_low,
                      quote.estimated_minutes_high,
                    )}
                  </div>
                </div>
                {dollarRange !== null && (
                  <div>
                    <div className="text-xs uppercase tracking-wide text-muted-foreground">
                      Cost range
                    </div>
                    <div
                      className="text-base font-medium"
                      data-testid="ps-detail-dollars"
                    >
                      {dollarRange}
                    </div>
                  </div>
                )}
              </div>

              <div>
                <div className="text-xs uppercase tracking-wide text-muted-foreground">
                  Narrative
                </div>
                <div
                  className="whitespace-pre-wrap text-sm"
                  data-testid="ps-detail-narrative"
                >
                  {quote.narrative}
                </div>
              </div>

              {quote.conversation_summary && (
                <div>
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">
                    Conversation summary
                  </div>
                  <div
                    className="whitespace-pre-wrap text-sm"
                    data-testid="ps-detail-conversation-summary"
                  >
                    {quote.conversation_summary}
                  </div>
                </div>
              )}

              {quote.flow_id && (
                <a
                  href={`/flow/${quote.flow_id}`}
                  className="inline-flex items-center gap-1 text-sm text-primary underline"
                  data-testid="ps-detail-open-flow"
                >
                  <ExternalLink
                    className="h-4 w-4"
                  />
                  Open flow
                </a>
              )}
            </div>

            {/* Right column — editable + actions */}
            <div className="space-y-6">
              <div>
                <div className="mb-1 text-sm font-medium">Org notes</div>
                <Textarea
                  value={orgNotes}
                  onChange={(e) => setOrgNotes(e.target.value)}
                  rows={4}
                  data-testid="ps-detail-org-notes"
                />
                <Button
                  size="sm"
                  className="mt-2"
                  onClick={() => submit({ org_notes: orgNotes })}
                  loading={update.isPending}
                  data-testid="ps-detail-save-org-notes"
                >
                  Save org notes
                </Button>
              </div>

              {isAdmin && (
                <div>
                  <div className="mb-1 text-sm font-medium">Admin notes</div>
                  <Textarea
                    value={adminNotes}
                    onChange={(e) => setAdminNotes(e.target.value)}
                    rows={4}
                    data-testid="ps-detail-admin-notes"
                  />
                  <Button
                    size="sm"
                    className="mt-2"
                    onClick={() => submit({ admin_notes: adminNotes })}
                    loading={update.isPending}
                    data-testid="ps-detail-save-admin-notes"
                  >
                    Save admin notes
                  </Button>
                </div>
              )}

              <div className="flex flex-wrap gap-2">
                {isAdmin && quote.status === "open" && (
                  <Button
                    variant="default"
                    onClick={() => submit({ status: "in_progress" })}
                    loading={update.isPending}
                    data-testid="ps-detail-mark-in-progress"
                  >
                    Mark in progress
                  </Button>
                )}
                {isAdmin && quote.status !== "closed" && (
                  <Button
                    variant="outline"
                    onClick={() => submit({ status: "closed" })}
                    loading={update.isPending}
                    data-testid="ps-detail-close"
                  >
                    Close
                  </Button>
                )}
                {isRequester && quote.status === "open" && (
                  <Button
                    variant="destructive"
                    onClick={() => submit({ status: "closed" })}
                    loading={update.isPending}
                    data-testid="ps-detail-cancel-request"
                  >
                    Cancel my request
                  </Button>
                )}
              </div>
            </div>
          </div>

          <footer
            className="mt-8 border-t pt-4 text-xs text-muted-foreground"
            data-testid="ps-detail-footer"
          >
            <div>Created: {formatDateTime(quote.created_at)}</div>
            <div>Submitted: {formatDateTime(quote.submitted_at)}</div>
            <div>In progress: {formatDateTime(quote.in_progress_at)}</div>
            <div>Closed: {formatDateTime(quote.closed_at)}</div>
            {quote.closed_by_user_id && (
              <div>Closed by user: {quote.closed_by_user_id}</div>
            )}
          </footer>
        </div>
      </div>
    </div>
  );
};

export default ProServiceQuoteDetailPage;
