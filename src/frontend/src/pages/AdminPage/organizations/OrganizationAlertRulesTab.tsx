import { useState } from "react";
import { Loader2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useCreateAlertRule } from "@/controllers/API/queries/admin/use-create-alert-rule";
import { useDeleteAlertRule } from "@/controllers/API/queries/admin/use-delete-alert-rule";
import { useGetAlertRules } from "@/controllers/API/queries/admin/use-get-alert-rules";
import { usePatchAlertRule } from "@/controllers/API/queries/admin/use-patch-alert-rule";

const RULE_TYPES = [
  { value: "consecutive_failures", label: "Consecutive failures" },
  { value: "error_rate", label: "Error rate" },
  { value: "sla_duration", label: "Run duration (SLA)" },
] as const;

const DEFAULT_COOLDOWN = 900; // 15 min

function describeConfig(
  ruleType: string,
  config: Record<string, unknown>,
): string {
  if (ruleType === "consecutive_failures") {
    return `after ${config.n ?? "?"} failures in a row`;
  }
  if (ruleType === "error_rate") {
    return `≥${config.rate_pct ?? "?"}% over ${config.window_minutes ?? "?"} min (min ${config.min_samples ?? "?"} runs)`;
  }
  if (ruleType === "sla_duration") {
    return `run exceeds ${config.max_seconds ?? "?"}s`;
  }
  return JSON.stringify(config);
}

export default function OrganizationAlertRulesTab({ orgId }: { orgId: string }) {
  const { data, isPending } = useGetAlertRules({ orgId });
  const create = useCreateAlertRule();
  const patch = usePatchAlertRule();
  const del = useDeleteAlertRule();

  const [ruleType, setRuleType] = useState<string>("consecutive_failures");
  const [cooldown, setCooldown] = useState<string>(String(DEFAULT_COOLDOWN));
  // consecutive_failures
  const [n, setN] = useState<string>("3");
  // error_rate
  const [ratePct, setRatePct] = useState<string>("50");
  const [windowMinutes, setWindowMinutes] = useState<string>("60");
  const [minSamples, setMinSamples] = useState<string>("5");
  // sla_duration
  const [maxSeconds, setMaxSeconds] = useState<string>("300");

  const items = data?.items ?? [];

  const onCreate = () => {
    let config: Record<string, unknown> = {};
    if (ruleType === "consecutive_failures") {
      const v = Number(n);
      if (!Number.isFinite(v) || v <= 0) return;
      config = { n: v };
    } else if (ruleType === "error_rate") {
      const pct = Number(ratePct);
      const win = Number(windowMinutes);
      const min = Number(minSamples);
      if (!Number.isFinite(pct) || pct <= 0 || pct > 100) return;
      if (!Number.isFinite(win) || win <= 0) return;
      if (!Number.isFinite(min) || min <= 0) return;
      config = { rate_pct: pct, window_minutes: win, min_samples: min };
    } else if (ruleType === "sla_duration") {
      const v = Number(maxSeconds);
      if (!Number.isFinite(v) || v <= 0) return;
      config = { max_seconds: v };
    }
    const cd = Number(cooldown);
    create.mutate({
      orgId,
      rule_type: ruleType,
      config,
      cooldown_seconds: Number.isFinite(cd) && cd >= 0 ? cd : DEFAULT_COOLDOWN,
    });
  };

  return (
    <div className="space-y-6">
      <div className="rounded-md border p-4">
        <h3 className="mb-3 font-medium">Add alert rule</h3>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_2fr_1fr_auto] md:items-end">
          <div className="flex flex-col gap-1">
            <Label htmlFor="rule-type">Rule type</Label>
            <Select value={ruleType} onValueChange={setRuleType}>
              <SelectTrigger id="rule-type" data-testid="rule-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {RULE_TYPES.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {ruleType === "consecutive_failures" && (
            <div className="flex flex-col gap-1">
              <Label htmlFor="rule-n">Failures in a row</Label>
              <Input
                id="rule-n"
                type="number"
                min={1}
                value={n}
                onChange={(e) => setN(e.target.value)}
                data-testid="rule-n"
              />
            </div>
          )}

          {ruleType === "error_rate" && (
            <div className="grid grid-cols-3 gap-2">
              <div className="flex flex-col gap-1">
                <Label htmlFor="rule-rate">Rate %</Label>
                <Input
                  id="rule-rate"
                  type="number"
                  min={1}
                  max={100}
                  value={ratePct}
                  onChange={(e) => setRatePct(e.target.value)}
                  data-testid="rule-rate"
                />
              </div>
              <div className="flex flex-col gap-1">
                <Label htmlFor="rule-window">Window (min)</Label>
                <Input
                  id="rule-window"
                  type="number"
                  min={1}
                  value={windowMinutes}
                  onChange={(e) => setWindowMinutes(e.target.value)}
                  data-testid="rule-window"
                />
              </div>
              <div className="flex flex-col gap-1">
                <Label htmlFor="rule-min">Min runs</Label>
                <Input
                  id="rule-min"
                  type="number"
                  min={1}
                  value={minSamples}
                  onChange={(e) => setMinSamples(e.target.value)}
                  data-testid="rule-min"
                />
              </div>
            </div>
          )}

          {ruleType === "sla_duration" && (
            <div className="flex flex-col gap-1">
              <Label htmlFor="rule-max">Max duration (s)</Label>
              <Input
                id="rule-max"
                type="number"
                min={1}
                value={maxSeconds}
                onChange={(e) => setMaxSeconds(e.target.value)}
                data-testid="rule-max"
              />
            </div>
          )}

          <div className="flex flex-col gap-1">
            <Label htmlFor="rule-cooldown">Cooldown (s)</Label>
            <Input
              id="rule-cooldown"
              type="number"
              min={0}
              value={cooldown}
              onChange={(e) => setCooldown(e.target.value)}
            />
          </div>

          <Button
            onClick={onCreate}
            disabled={create.isPending}
            data-testid="rule-create"
          >
            Add
          </Button>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          New rules apply org-wide. Flow-specific rules appear in the list when
          created via API.
        </p>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Type</TableHead>
              <TableHead>Condition</TableHead>
              <TableHead>Scope</TableHead>
              <TableHead>Cooldown (s)</TableHead>
              <TableHead>Active</TableHead>
              <TableHead>Last fired</TableHead>
              <TableHead className="w-[60px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isPending ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  <Loader2
                    className="mx-auto h-5 w-5 animate-spin"
                  />
                </TableCell>
              </TableRow>
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={7}
                  className="text-center text-sm text-muted-foreground"
                >
                  No alert rules configured.
                </TableCell>
              </TableRow>
            ) : (
              items.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-medium">
                    {RULE_TYPES.find((t) => t.value === r.rule_type)?.label ??
                      r.rule_type}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {describeConfig(r.rule_type, r.config)}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {r.flow_id ? `flow ${r.flow_id.slice(0, 8)}…` : "org-wide"}
                  </TableCell>
                  <TableCell>{r.cooldown_seconds}</TableCell>
                  <TableCell>
                    <Switch
                      checked={r.is_active}
                      onCheckedChange={(checked) =>
                        patch.mutate({ id: r.id, is_active: checked })
                      }
                      data-testid={`rule-active-${r.id}`}
                    />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {r.last_fired_at
                      ? new Date(r.last_fired_at).toLocaleString()
                      : "—"}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => del.mutate({ id: r.id })}
                      data-testid={`rule-delete-${r.id}`}
                      aria-label="Delete alert rule"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
