import { describe, expect, it } from "vitest";

import { cn, estimateSize, formatNumber, titleCase } from "./utils";

describe("frontend utility functions", () => {
  it("formats catalog identifiers for display", () => {
    expect(titleCase("rare_high_value_activity")).toBe("Rare High Value Activity");
  });

  it("merges conflicting Tailwind classes", () => {
    expect(cn("px-2", "px-4", "font-medium")).toBe("px-4 font-medium");
  });

  it("formats numbers using the product locale", () => {
    expect(formatNumber(12500)).toBe("12,500");
    expect(formatNumber(undefined)).toBe("0");
  });

  it("estimates output sizes without returning negative or zero values", () => {
    expect(estimateSize(10_000, ["patients", "claims"], "csv", "healthcare")).toBeGreaterThan(0);
    expect(estimateSize(0, 0, "csv")).toBe(0);
  });
});
