"use client";

import { ProjectionChart, ScenarioChart, TornadoChart } from "@/components/charts";
import { Figure, Notice, Panel, Section } from "@/components/common";
import { Ledger } from "@/components/ledger";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatValue, money, pct, signClass } from "@/lib/format";
import type { DealResults } from "@/lib/types";
import { cn } from "@/lib/utils";

export function HeadlineFigures({ r }: { r: DealResults }) {
  const v = (k: string) => r.metrics.find((m) => m.key === k)?.value ?? null;
  const cf = v("monthly_cash_flow");
  const cfTax = v("monthly_cash_flow_after_tax");
  return (
    <div className="grid grid-cols-2 gap-x-6 gap-y-5 border-y border-rule py-5 md:grid-cols-5">
      <Figure label="Gross yield" value={pct(v("gross_yield"))} sub={`Net ${pct(v("net_yield"))}`} />
      <Figure
        label="Monthly cash flow"
        value={formatValue(cf, "gbp")}
        tone={cf !== null && cf < 0 ? "neg" : "pos"}
        sub={`${formatValue(cfTax, "gbp")} after estimated tax`}
      />
      <Figure label="Cash needed upfront" value={money(v("initial_cash_required"))} sub="Deposit, tax and fees" />
      <Figure label="Cash-on-cash" value={pct(v("cash_on_cash"))} sub="Year one, pre-tax" />
      <Figure
        label={`IRR over ${r.inputs.holding_years} years`}
        value={pct(v("irr"))}
        sub="Estimate, after tax"
        tone={(v("irr") ?? 0) < 0 ? "neg" : undefined}
      />
    </div>
  );
}

export function Warnings({ r }: { r: DealResults }) {
  const important = r.warnings;
  if (!important.length) return null;
  return (
    <Notice tone="warn" title="Check these before relying on the figures" className="mt-6">
      <ul className="list-disc space-y-1 pl-4">
        {important.map((w) => (
          <li key={w}>{w}</li>
        ))}
      </ul>
    </Notice>
  );
}

export function AnalysisBody({ r }: { r: DealResults }) {
  const tt = r.transaction_tax;
  const taxWarnings = r.tax_notes ?? [];
  return (
    <>
      <Section
        title="The figures"
        description="Select any line to see the formula and the inputs behind it. Lines marked estimate depend on tax rules or your growth assumptions."
        className="mt-8"
      >
        <div className="grid gap-x-10 gap-y-6 lg:grid-cols-2">
          <div>
            <h3 className="mb-1 text-sm font-semibold text-slate">Buying</h3>
            <Ledger
              metrics={r.metrics}
              keys={["deposit", "transaction_tax", "loan_amount", "ltv", "initial_cash_required"]}
              emphasis={["initial_cash_required"]}
            />
            <h3 className="mb-1 mt-6 text-sm font-semibold text-slate">Income and running costs (year one)</h3>
            <Ledger
              metrics={r.metrics}
              keys={["annual_rent", "collected_rent", "operating_expenses", "noi_annual", "gross_yield", "net_yield", "net_yield_on_cost"]}
              emphasis={["noi_annual"]}
            />
          </div>
          <div>
            <h3 className="mb-1 text-sm font-semibold text-slate">Financing and cash flow</h3>
            <Ledger
              metrics={r.metrics}
              keys={[
                "monthly_mortgage_payment",
                "monthly_cash_flow",
                "annual_cash_flow",
                "annual_tax",
                "monthly_cash_flow_after_tax",
                "cash_on_cash",
                "icr",
                "max_loan_by_icr",
              ]}
              emphasis={["monthly_cash_flow"]}
            />
            <h3 className="mb-1 mt-6 text-sm font-semibold text-slate">Over the holding period</h3>
            <Ledger metrics={r.metrics} keys={["irr", "total_profit", "equity_multiple"]} emphasis={["irr"]} />
          </div>
        </div>
      </Section>

      <Section title="What would need to change" description="Break-even points found by re-running the calculation with one input changed at a time.">
        <div className="grid gap-px overflow-hidden rounded-xl border border-rule bg-rule sm:grid-cols-2 lg:grid-cols-3">
          {r.break_even.map((b) => (
            <div key={b.key} className="bg-card p-4">
              <p className="text-[13px] text-slate">{b.label}</p>
              <p className="num font-heading mt-1 text-xl font-semibold text-ink">{formatValue(b.value, b.unit)}</p>
              <p className="num mt-0.5 text-xs text-slate">Currently {formatValue(b.current, b.unit)}</p>
              <p className="mt-2 text-xs leading-relaxed text-slate">{b.explanation}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section
        title="Sensitivity"
        description="How monthly cash flow moves when each assumption changes on its own. Bars show the change from the base case."
      >
        <Panel>
          <TornadoChart rows={r.sensitivity.rows} base={r.sensitivity.base.monthly_cash_flow} />
          <Table className="mt-4">
            <TableHeader>
              <TableRow>
                <TableHead>Assumption</TableHead>
                <TableHead>Change tested</TableHead>
                <TableHead className="text-right">Downside cash flow</TableHead>
                <TableHead className="text-right">Upside cash flow</TableHead>
                <TableHead className="text-right">IRR range</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {r.sensitivity.rows.map((s) => (
                <TableRow key={s.driver}>
                  <TableCell className="font-medium">{s.driver}</TableCell>
                  <TableCell className="text-slate">{s.description}</TableCell>
                  <TableCell className={cn("num text-right", signClass(s.low.monthly_cash_flow))}>{money(s.low.monthly_cash_flow)}</TableCell>
                  <TableCell className={cn("num text-right", signClass(s.high.monthly_cash_flow))}>{money(s.high.monthly_cash_flow)}</TableCell>
                  <TableCell className="num text-right">
                    {pct(s.low.irr_pct, 1)} to {pct(s.high.irr_pct, 1)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Panel>
      </Section>

      <Section
        title="Scenarios"
        description="Optimistic and pessimistic cases change several assumptions at once. The drivers list shows each change's effect on its own."
      >
        <div className="grid gap-6 lg:grid-cols-[minmax(0,360px)_1fr]">
          <Panel>
            <ScenarioChart data={r.scenarios.map((s) => ({ name: s.name, irr: s.irr_pct, cashflow: s.monthly_cash_flow }))} />
          </Panel>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Scenario</TableHead>
                  <TableHead className="text-right">Cash flow /mo</TableHead>
                  <TableHead className="text-right">Net yield</TableHead>
                  <TableHead className="text-right">IRR</TableHead>
                  <TableHead>Biggest drivers</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {r.scenarios.map((s) => (
                  <TableRow key={s.name}>
                    <TableCell className="font-medium">{s.name}</TableCell>
                    <TableCell className={cn("num text-right", signClass(s.monthly_cash_flow))}>{money(s.monthly_cash_flow)}</TableCell>
                    <TableCell className="num text-right">{pct(s.net_yield_pct)}</TableCell>
                    <TableCell className="num text-right">{pct(s.irr_pct)}</TableCell>
                    <TableCell className="text-xs text-slate">
                      {s.drivers.length
                        ? s.drivers
                            .slice(0, 3)
                            .map((d) => `${d.assumption} ${d.irr_impact_pp !== null ? `${d.irr_impact_pp > 0 ? "+" : ""}${d.irr_impact_pp}pp IRR` : ""}`)
                            .join(", ")
                        : "Your inputs"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      </Section>

      <Section title={`${r.inputs.holding_years}-year projection`} description="Bars are after-tax cash flow each year; the line is your equity (value minus loan).">
        <Panel>
          <ProjectionChart data={r.projection} />
        </Panel>
        <div className="mt-4 overflow-x-auto">
          <Table className="min-w-[760px]">
            <TableHeader>
              <TableRow>
                {["Year", "Collected rent", "Running costs", "Mortgage", "Pre-tax", "Tax (est.)", "After tax", "Value", "Loan"].map((h) => (
                  <TableHead key={h} className={h === "Year" ? "" : "text-right"}>
                    {h}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {r.projection.map((p) => (
                <TableRow key={p.year}>
                  <TableCell>{p.year}</TableCell>
                  {[p.collected_rent, p.operating_expenses, p.debt_service, p.pre_tax_cash_flow, p.tax, p.after_tax_cash_flow, p.property_value, p.loan_balance].map((v, i) => (
                    <TableCell key={i} className={cn("num text-right", (i === 3 || i === 5) && signClass(v))}>
                      {money(v)}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Section>

      <div className="grid gap-10 lg:grid-cols-2">
        <Section title={`${tt.name}${tt.overridden ? " (your figure)" : " estimate"}`} description={`Rules reviewed ${tt.rules_reviewed_on}.`}>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Band</TableHead>
                <TableHead className="text-right">Rate</TableHead>
                <TableHead className="text-right">Taxable</TableHead>
                <TableHead className="text-right">Tax</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tt.bands.map((b) => (
                <TableRow key={b.lower}>
                  <TableCell className="num">
                    {money(b.lower)} to {b.upper ? money(b.upper) : "above"}
                  </TableCell>
                  <TableCell className="num text-right">{b.rate_pct}%</TableCell>
                  <TableCell className="num text-right">{money(b.taxable_amount)}</TableCell>
                  <TableCell className="num text-right">{money(b.tax)}</TableCell>
                </TableRow>
              ))}
              <TableRow>
                <TableCell className="font-semibold">Total ({pct(tt.effective_rate_pct)} effective)</TableCell>
                <TableCell />
                <TableCell />
                <TableCell className="num text-right font-semibold">{money(tt.total)}</TableCell>
              </TableRow>
            </TableBody>
          </Table>
          <ul className="mt-3 list-disc space-y-1 pl-4 text-xs leading-relaxed text-slate">
            {tt.assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
          <a href={tt.source_url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-xs font-medium text-wood underline underline-offset-2">
            Official rates and guidance
          </a>
        </Section>

        <Section title={`Selling in year ${r.sale.year}`} description="Estimated exit, with capital gains tax as a simplified scenario.">
          <div>
            {[
              ["Sale price", r.sale.sale_price],
              ["Selling costs", -r.sale.selling_costs],
              ["Loan repaid", -r.sale.loan_repayment],
              ["Capital gains tax (estimate)", -r.sale.capital_gains_tax],
            ].map(([k, v]) => (
              <div key={k as string} className="flex items-baseline gap-2 border-b border-rule py-2.5 text-sm">
                <span>{k}</span>
                <span className="leader" aria-hidden />
                <span className="num font-medium">{money(v as number)}</span>
              </div>
            ))}
            <div className="flex items-baseline gap-2 py-2.5">
              <span className="font-semibold">Net sale proceeds</span>
              <span className="leader" aria-hidden />
              <span className="num text-lg font-semibold">{money(r.sale.net_sale_proceeds)}</span>
            </div>
            <p className="mt-1 text-xs text-slate">
              Gain before tax {money(r.sale.gain)} on a base cost of {money(r.sale.base_cost)}. {r.sale.cgt_formula}
            </p>
          </div>
        </Section>
      </div>

      <Section title="Assumptions and limitations">
        <div className="grid gap-6 lg:grid-cols-2">
          <ul className="list-disc space-y-1.5 pl-4 text-sm leading-relaxed text-slate">
            {r.assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
          <div className="space-y-2 text-sm leading-relaxed text-slate">
            {taxWarnings.map((w) => (
              <p key={w}>{w}</p>
            ))}
            <p className="text-xs">
              Engine v{r.engine_version}. Tax rules reviewed {r.tax_rules_reviewed_on}.
            </p>
          </div>
        </div>
      </Section>
    </>
  );
}
