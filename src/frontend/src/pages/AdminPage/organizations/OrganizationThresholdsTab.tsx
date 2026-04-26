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
import { useCreateUsageThreshold } from "@/controllers/API/queries/admin/use-create-usage-threshold";
import { useDeleteUsageThreshold } from "@/controllers/API/queries/admin/use-delete-usage-threshold";
import { useGetUsageThresholds } from "@/controllers/API/queries/admin/use-get-usage-thresholds";
import { usePatchUsageThreshold } from "@/controllers/API/queries/admin/use-patch-usage-threshold";

const METRICS = [
  { value: "runs", label: "Runs" },
  { value: "run_seconds", label: "Run seconds" },
  { value: "tokens", label: "Tokens" },
] as const;

const PERIODS = [
  { value: "daily", label: "Daily" },
  { value: "monthly", label: "Monthly" },
] as const;

const DEFAULT_COOLDOWN = 3600; // 1 hour

export default function OrganizationThresholdsTab({ orgId }: { orgId: string }) {
  const { data, isPending } = useGetUsageThresholds({ orgId });
  const create = useCreateUsageThreshold();
  const patch = usePatchUsageThreshold();
  const del = useDeleteUsageThreshold();

  const [metric, setMetric] = useState<string>("runs");
  const [period, setPeriod] = useState<string>("daily");
  const [thresholdValue, setThresholdValue] = useState<string>("");
  const [cooldown, setCooldown] = useState<string>(String(DEFAULT_COOLDOWN));

  const items = data?.items ?? [];

  const onCreate = () => {
    const value = Number(thresholdValue);
    if (!Number.isFinite(value) || value <= 0) return;
    const cd = Number(cooldown);
    create.mutate(
      {
        orgId,
        metric,
        period,
        threshold_value: value,
        cooldown_seconds: Number.isFinite(cd) && cd >= 0 ? cd : DEFAULT_COOLDOWN,
      },
      {
        onSuccess: () => {
          setThresholdValue("");
        },
      },
    );
  };

  return (
    <div className="space-y-6">
      <div className="rounded-md border p-4">
        <h3 className="mb-3 font-medium">Add threshold</h3>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_1fr_1fr_1fr_auto]">
          <div className="flex flex-col gap-1">
            <Label htmlFor="threshold-metric">Metric</Label>
            <Select value={metric} onValueChange={setMetric}>
              <SelectTrigger id="threshold-metric" data-testid="threshold-metric">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {METRICS.map((m) => (
                  <SelectItem key={m.value} value={m.value}>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="threshold-period">Period</Label>
            <Select value={period} onValueChange={setPeriod}>
              <SelectTrigger id="threshold-period" data-testid="threshold-period">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PERIODS.map((p) => (
                  <SelectItem key={p.value} value={p.value}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="threshold-value">Threshold</Label>
            <Input
              id="threshold-value"
              type="number"
              min={1}
              value={thresholdValue}
              onChange={(e) => setThresholdValue(e.target.value)}
              placeholder="e.g. 1000"
              data-testid="threshold-value"
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="threshold-cooldown">Cooldown (s)</Label>
            <Input
              id="threshold-cooldown"
              type="number"
              min={0}
              value={cooldown}
              onChange={(e) => setCooldown(e.target.value)}
            />
          </div>
          <div className="flex items-end">
            <Button
              onClick={onCreate}
              disabled={create.isPending || !thresholdValue}
              data-testid="threshold-create"
            >
              Add
            </Button>
          </div>
        </div>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Metric</TableHead>
              <TableHead>Period</TableHead>
              <TableHead>Threshold</TableHead>
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
                  No thresholds configured.
                </TableCell>
              </TableRow>
            ) : (
              items.map((t) => (
                <TableRow key={t.id}>
                  <TableCell className="font-medium">
                    {METRICS.find((m) => m.value === t.metric)?.label ?? t.metric}
                  </TableCell>
                  <TableCell>
                    {PERIODS.find((p) => p.value === t.period)?.label ?? t.period}
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      min={1}
                      defaultValue={t.threshold_value}
                      onBlur={(e) => {
                        const v = Number(e.target.value);
                        if (Number.isFinite(v) && v > 0 && v !== t.threshold_value) {
                          patch.mutate({ id: t.id, threshold_value: v });
                        }
                      }}
                      className="w-28"
                      data-testid={`threshold-value-${t.id}`}
                    />
                  </TableCell>
                  <TableCell>{t.cooldown_seconds}</TableCell>
                  <TableCell>
                    <Switch
                      checked={t.is_active}
                      onCheckedChange={(checked) =>
                        patch.mutate({ id: t.id, is_active: checked })
                      }
                      data-testid={`threshold-active-${t.id}`}
                    />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {t.last_fired_at
                      ? new Date(t.last_fired_at).toLocaleString()
                      : "—"}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => del.mutate({ id: t.id })}
                      data-testid={`threshold-delete-${t.id}`}
                      aria-label="Delete threshold"
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
