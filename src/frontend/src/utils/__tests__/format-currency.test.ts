import { formatUsdFromMicros } from "../format-currency";

describe("formatUsdFromMicros", () => {
  it("returns null for null input", () => {
    expect(formatUsdFromMicros(null)).toBeNull();
  });

  it("returns null for undefined input", () => {
    expect(formatUsdFromMicros(undefined)).toBeNull();
  });

  it("returns null for negative input (defensive)", () => {
    expect(formatUsdFromMicros(-1)).toBeNull();
  });

  it("formats genuine zero as $0.00", () => {
    expect(formatUsdFromMicros(0)).toBe("$0.00");
  });

  it("formats sub-cent positives as <$0.01", () => {
    expect(formatUsdFromMicros(1)).toBe("<$0.01");
    expect(formatUsdFromMicros(9_999)).toBe("<$0.01");
  });

  it("formats one cent as $0.01", () => {
    expect(formatUsdFromMicros(10_000)).toBe("$0.01");
  });

  it("formats multi-cent values as $X.XX", () => {
    expect(formatUsdFromMicros(1_234_567)).toBe("$1.23");
    expect(formatUsdFromMicros(99_990_000)).toBe("$99.99");
  });

  it("rounds half-cent up to next cent", () => {
    expect(formatUsdFromMicros(15_000)).toBe("$0.02");
  });
});
