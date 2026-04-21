import { describe, expect, it } from "@jest/globals";
import { formatRelativeTime } from "../formatRelativeTime";

const NOW = new Date("2026-04-21T12:00:00Z");

function iso(offsetSeconds: number): string {
  return new Date(NOW.getTime() - offsetSeconds * 1000).toISOString();
}

describe("formatRelativeTime", () => {
  it("returns 'just now' for < 60 seconds", () => {
    expect(formatRelativeTime(iso(0), NOW)).toBe("just now");
    expect(formatRelativeTime(iso(59), NOW)).toBe("just now");
  });

  it("returns minutes for 60s to 59m59s, singular at 1 minute", () => {
    expect(formatRelativeTime(iso(60), NOW)).toBe("1 minute ago");
    expect(formatRelativeTime(iso(119), NOW)).toBe("1 minute ago");
    expect(formatRelativeTime(iso(120), NOW)).toBe("2 minutes ago");
    expect(formatRelativeTime(iso(3599), NOW)).toBe("59 minutes ago");
  });

  it("returns hours for 1h to 23h59m, singular at 1 hour", () => {
    expect(formatRelativeTime(iso(3600), NOW)).toBe("1 hour ago");
    expect(formatRelativeTime(iso(7199), NOW)).toBe("1 hour ago");
    expect(formatRelativeTime(iso(7200), NOW)).toBe("2 hours ago");
    expect(formatRelativeTime(iso(86399), NOW)).toBe("23 hours ago");
  });

  it("returns days for 1d to 29d, singular at 1 day", () => {
    expect(formatRelativeTime(iso(86400), NOW)).toBe("1 day ago");
    expect(formatRelativeTime(iso(86400 * 2), NOW)).toBe("2 days ago");
    expect(formatRelativeTime(iso(86400 * 29), NOW)).toBe("29 days ago");
  });

  it("returns 'on {date}' for >= 30 days", () => {
    const past = iso(86400 * 30);
    const result = formatRelativeTime(past, NOW);
    expect(result).toMatch(/^on /);
    // Verify the date string is the localized toLocaleDateString output
    expect(result).toBe(
      `on ${new Date(past).toLocaleDateString()}`,
    );
  });

  it("handles a future timestamp by treating it as 'just now'", () => {
    // Defensive: clock skew shouldn't produce negative-minutes nonsense.
    expect(formatRelativeTime(iso(-30), NOW)).toBe("just now");
  });
});
