import { describe, expect, it } from "vitest";

import { compactMoney, formatInput, formatValue, money, pct, signClass } from "@/lib/format";

describe("money", () => {
  it("formats whole pounds with a true minus sign", () => {
    expect(money(1234.56)).toBe("£1,235");
    expect(money(-250)).toBe("−£250");
    expect(money(65.12)).toBe("£65");
    expect(money(65.12, { pence: true })).toBe("£65.12");
  });
  it("handles missing values", () => {
    expect(money(null)).toBe("n/a");
    expect(money(undefined)).toBe("n/a");
    expect(money(Number.NaN)).toBe("n/a");
  });
  it("compacts large amounts", () => {
    expect(compactMoney(1_250_000)).toBe("£1.25m");
    expect(compactMoney(245_000)).toBe("£245k");
    expect(compactMoney(950)).toBe("£950");
  });
});

describe("pct and formatValue", () => {
  it("formats percentages", () => {
    expect(pct(6.6)).toBe("6.60%");
    expect(pct(-5.21, 1)).toBe("−5.2%");
    expect(pct(null)).toBe("n/a");
  });
  it("formats by unit", () => {
    expect(formatValue(625, "gbp_month")).toBe("£625/mo");
    expect(formatValue(1.687, "multiple")).toBe("1.69×");
    expect(formatValue(null, "percent")).toBe("n/a");
  });
  it("formats engine inputs for the working panel", () => {
    expect(formatInput("deposit_pct", 25)).toBe("25%");
    expect(formatInput("term_years", 25)).toBe("25 years");
    expect(formatInput("purchase_price", 200000)).toBe("£200,000");
    expect(formatInput("mortgage_type", "interest_only")).toBe("interest only");
    expect(formatInput("non_resident", false)).toBe("no");
  });
  it("colours signed figures", () => {
    expect(signClass(-1)).toBe("text-brick");
    expect(signClass(1)).toBe("text-wood");
    expect(signClass(0)).toBe("");
  });
});
