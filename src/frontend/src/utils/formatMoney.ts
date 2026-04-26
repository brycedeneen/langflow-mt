/**
 * Format a USD-denominated amount for display.
 *
 * The pro-service-quote API serialises Decimal values as JSON strings
 * (e.g. ``"200.00"``) to avoid IEEE-754 round-tripping; this helper accepts
 * either the raw string or a number and renders it in the project-standard
 * ``$X.XX`` form.
 *
 * - ``null`` / ``undefined`` / unparsable strings return ``"—"`` (em-dash).
 * - Strictly-positive sub-cent values render ``"<$0.01"`` (never ``$0.00``,
 *   so a non-zero cost is never silently rounded away).
 * - Zero renders ``"$0.00"`` exactly (as a definite "free", not "rounded").
 *
 * Note: this complements ``format-currency.ts``'s
 * ``formatUsdFromMicros`` which is used by the per-build cost telemetry
 * that stores micros as integers. PS quotes carry plain dollar Decimals so
 * we keep a separate formatter rather than convert at the boundary.
 */
export function formatUSD(amount: string | number | null | undefined): string {
  if (amount === null || amount === undefined) return "—";
  const n = typeof amount === "string" ? parseFloat(amount) : amount;
  if (Number.isNaN(n)) return "—";
  if (n > 0 && n < 0.01) return "<$0.01";
  return `$${n.toFixed(2)}`;
}
