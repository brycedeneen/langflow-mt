/**
 * Format an ISO timestamp relative to a reference point (default: now).
 * Thresholds:
 *   < 60s          -> "just now"
 *   < 60m          -> "N minutes ago" (singular at 1)
 *   < 24h          -> "N hours ago"   (singular at 1)
 *   < 30d          -> "N days ago"    (singular at 1)
 *   >= 30d         -> "on {locale date}"
 * A future timestamp (ref < iso) is treated as "just now" to avoid negative-time
 * artifacts from clock skew.
 */
export function formatRelativeTime(
  iso: string,
  now: Date = new Date(),
): string {
  const then = new Date(iso);
  const elapsedSec = Math.floor((now.getTime() - then.getTime()) / 1000);

  if (elapsedSec < 60) return "just now";

  const minutes = Math.floor(elapsedSec / 60);
  if (minutes < 60) return minutes === 1 ? "1 minute ago" : `${minutes} minutes ago`;

  const hours = Math.floor(elapsedSec / 3600);
  if (hours < 24) return hours === 1 ? "1 hour ago" : `${hours} hours ago`;

  const days = Math.floor(elapsedSec / 86400);
  if (days < 30) return days === 1 ? "1 day ago" : `${days} days ago`;

  return `on ${then.toLocaleDateString()}`;
}
