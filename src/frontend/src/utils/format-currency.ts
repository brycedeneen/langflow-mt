export function formatUsdFromMicros(
  micros: number | null | undefined,
): string | null {
  if (micros == null) return null;
  if (micros < 0) return null;
  if (micros === 0) return "$0.00";
  if (micros < 10_000) return "<$0.01";
  // Round in integer-cent space to avoid IEEE-754 surprises with toFixed(2).
  const cents = Math.round(micros / 10_000);
  return `$${(cents / 100).toFixed(2)}`;
}
