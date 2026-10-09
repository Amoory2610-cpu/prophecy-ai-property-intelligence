import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Ledger } from "@/components/ledger";
import type { Metric } from "@/lib/types";

const metrics: Metric[] = [
  {
    key: "monthly_cash_flow",
    label: "Monthly cash flow after financing (pre-tax)",
    value: -120.5,
    unit: "gbp_month",
    formula: "(net operating income - annual mortgage payments) ÷ 12",
    inputs: { net_operating_income: 10021.2, debt_service: 11467 },
    basis: "calculated",
    note: null,
  },
  {
    key: "annual_tax",
    label: "Estimated tax on rental profit (year 1)",
    value: 2508.48,
    unit: "gbp",
    formula: "tax = ...",
    inputs: { tax_band: "higher" },
    basis: "estimate",
    note: "Simplified scenario - not tax advice.",
  },
];

describe("Ledger", () => {
  it("shows values, marks estimates and colours negatives", () => {
    render(<Ledger metrics={metrics} keys={["monthly_cash_flow", "annual_tax"]} />);
    const cf = screen.getByText("−£121/mo");
    expect(cf).toHaveClass("text-brick");
    expect(screen.getAllByText("estimate")).toHaveLength(1);
  });

  it("reveals the working with real inputs when a line is selected", () => {
    render(<Ledger metrics={metrics} keys={["monthly_cash_flow"]} />);
    const row = screen.getByRole("button", { name: /Monthly cash flow/ });
    expect(row).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(row);
    expect(row).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText(/annual mortgage payments\) ÷ 12/)).toBeInTheDocument();
    expect(screen.getByText("£10,021")).toBeInTheDocument();
    expect(screen.getByText("debt service")).toBeInTheDocument();
  });

  it("skips keys that are not present", () => {
    render(<Ledger metrics={metrics} keys={["missing", "annual_tax"]} />);
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });
});
