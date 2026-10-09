"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { compactMoney, money, pct } from "@/lib/format";
import type { ProjectionYear, SensitivityRow } from "@/lib/types";

const INK = "#16212c";
const SLATE = "#5a6a79";
const RULE = "#d5dce3";
const WOOD = "#2e5e4e";
const BRICK = "#a3442a";
const BLUE = "#3f6f9a";

const axis = { stroke: RULE, tick: { fill: SLATE, fontSize: 12 }, tickLine: false };

function Frame({ height = 280, label, children }: { height?: number; label: string; children: React.ReactElement }) {
  return (
    <div role="img" aria-label={label} style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        {children}
      </ResponsiveContainer>
    </div>
  );
}

function TooltipBox({ title, rows }: { title: string; rows: [string, string, string?][] }) {
  return (
    <div className="rounded-md border border-rule bg-card px-3 py-2 text-xs shadow-sm">
      <p className="mb-1 font-semibold text-ink">{title}</p>
      {rows.map(([k, v, colour]) => (
        <p key={k} className="num flex justify-between gap-4 text-slate">
          <span className="flex items-center gap-1.5">
            {colour && <span className="inline-block size-2 rounded-full" style={{ background: colour }} />}
            {k}
          </span>
          <span className="text-ink">{v}</span>
        </p>
      ))}
    </div>
  );
}

/** Annual after-tax cash flow (bars, signed colour) with equity build-up (line, right axis). */
export function ProjectionChart({ data }: { data: ProjectionYear[] }) {
  return (
    <Frame label="Projected annual cash flow and equity by year" height={300}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
        <CartesianGrid stroke={RULE} vertical={false} strokeDasharray="2 4" />
        <XAxis dataKey="year" {...axis} tickFormatter={(y) => `Yr ${y}`} />
        <YAxis yAxisId="cf" {...axis} width={64} tickFormatter={compactMoney} />
        <YAxis yAxisId="eq" orientation="right" {...axis} width={64} tickFormatter={compactMoney} />
        <ReferenceLine yAxisId="cf" y={0} stroke={INK} strokeWidth={1} />
        <Tooltip
          cursor={{ fill: "rgba(22,33,44,0.04)" }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const p = payload[0].payload as ProjectionYear;
            return (
              <TooltipBox
                title={`Year ${p.year}`}
                rows={[
                  ["After-tax cash flow", money(p.after_tax_cash_flow), p.after_tax_cash_flow < 0 ? BRICK : WOOD],
                  ["Equity", money(p.equity), BLUE],
                  ["Property value", money(p.property_value)],
                  ["Loan balance", money(p.loan_balance)],
                ]}
              />
            );
          }}
        />
        <Bar yAxisId="cf" dataKey="after_tax_cash_flow" radius={[3, 3, 0, 0]} maxBarSize={34}>
          {data.map((d) => (
            <Cell key={d.year} fill={d.after_tax_cash_flow < 0 ? BRICK : WOOD} />
          ))}
        </Bar>
        <Line yAxisId="eq" type="monotone" dataKey="equity" stroke={BLUE} strokeWidth={2} dot={false} />
      </ComposedChart>
    </Frame>
  );
}

/** Tornado: monthly cash flow at each driver's downside and upside, relative to base. */
export function TornadoChart({ rows, base }: { rows: SensitivityRow[]; base: number }) {
  const data = rows.map((r) => ({
    driver: r.driver,
    low: r.low.monthly_cash_flow - base,
    high: r.high.monthly_cash_flow - base,
    lowLabel: r.low.label,
    highLabel: r.high.label,
    lowAbs: r.low.monthly_cash_flow,
    highAbs: r.high.monthly_cash_flow,
  }));
  return (
    <Frame label="Sensitivity of monthly cash flow to each assumption" height={44 * rows.length + 40}>
      <BarChart data={data} layout="vertical" stackOffset="sign" margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
        <CartesianGrid stroke={RULE} horizontal={false} strokeDasharray="2 4" />
        <XAxis type="number" {...axis} tickFormatter={(v) => `${v > 0 ? "+" : ""}${compactMoney(v)}`} />
        <YAxis type="category" dataKey="driver" {...axis} width={110} />
        <ReferenceLine x={0} stroke={INK} />
        <Tooltip
          cursor={{ fill: "rgba(22,33,44,0.04)" }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const d = payload[0].payload as (typeof data)[number];
            return (
              <TooltipBox
                title={d.driver}
                rows={[
                  [`Downside (${d.lowLabel})`, `${money(d.lowAbs)}/mo`, BRICK],
                  [`Upside (${d.highLabel})`, `${money(d.highAbs)}/mo`, WOOD],
                  ["Base case", `${money(base)}/mo`],
                ]}
              />
            );
          }}
        />
        <Bar dataKey="low" stackId="s" fill={BRICK} radius={2} maxBarSize={22} />
        <Bar dataKey="high" stackId="s" fill={WOOD} radius={2} maxBarSize={22} />
      </BarChart>
    </Frame>
  );
}

export function TrendChart({
  points,
}: {
  points: { month: string; median: number | null; count: number; low_sample: boolean }[];
}) {
  return (
    <Frame label="Monthly median sale price and number of sales" height={300}>
      <ComposedChart data={points} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
        <CartesianGrid stroke={RULE} vertical={false} strokeDasharray="2 4" />
        <XAxis dataKey="month" {...axis} minTickGap={24} />
        <YAxis yAxisId="p" {...axis} width={64} tickFormatter={compactMoney} domain={["auto", "auto"]} />
        <YAxis yAxisId="n" orientation="right" {...axis} width={44} />
        <Tooltip
          cursor={{ fill: "rgba(22,33,44,0.04)" }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const p = payload[0].payload as (typeof points)[number];
            return (
              <TooltipBox
                title={p.month}
                rows={[
                  ["Median price", money(p.median), WOOD],
                  ["Sales recorded", String(p.count), RULE],
                  ...(p.low_sample ? ([["Note", "fewer than 10 sales"]] as [string, string][]) : []),
                ]}
              />
            );
          }}
        />
        <Bar yAxisId="n" dataKey="count" fill={RULE} maxBarSize={26} radius={[2, 2, 0, 0]} />
        <Line
          yAxisId="p"
          type="monotone"
          dataKey="median"
          stroke={WOOD}
          strokeWidth={2}
          connectNulls
          dot={(props) => {
            const { cx, cy, payload, index } = props as { cx: number; cy: number; payload: { low_sample: boolean }; index: number };
            return (
              <circle
                key={index}
                cx={cx}
                cy={cy}
                r={3}
                fill={payload.low_sample ? "#fff" : WOOD}
                stroke={WOOD}
                strokeWidth={1.5}
              />
            );
          }}
        />
      </ComposedChart>
    </Frame>
  );
}

export function HistogramChart({ bins }: { bins: { from: number; to: number; count: number }[] }) {
  const data = bins.map((b) => ({ ...b, label: compactMoney(b.from) }));
  return (
    <Frame label="Distribution of sale prices" height={240}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 4, bottom: 0 }} barCategoryGap={1}>
        <CartesianGrid stroke={RULE} vertical={false} strokeDasharray="2 4" />
        <XAxis dataKey="label" {...axis} minTickGap={16} />
        <YAxis {...axis} width={44} />
        <Tooltip
          cursor={{ fill: "rgba(22,33,44,0.04)" }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const b = payload[0].payload as (typeof data)[number];
            return <TooltipBox title={`${money(b.from)} to ${money(b.to)}`} rows={[["Sales", String(b.count), BLUE]]} />;
          }}
        />
        <Bar dataKey="count" fill={BLUE} radius={[2, 2, 0, 0]} />
      </BarChart>
    </Frame>
  );
}

export function ScenarioChart({ data }: { data: { name: string; irr: number | null; cashflow: number }[] }) {
  return (
    <Frame label="Monthly cash flow by scenario" height={200}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
        <CartesianGrid stroke={RULE} vertical={false} strokeDasharray="2 4" />
        <XAxis dataKey="name" {...axis} />
        <YAxis {...axis} width={60} tickFormatter={compactMoney} />
        <ReferenceLine y={0} stroke={INK} />
        <Tooltip
          cursor={{ fill: "rgba(22,33,44,0.04)" }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const d = payload[0].payload as (typeof data)[number];
            return (
              <TooltipBox
                title={d.name}
                rows={[
                  ["Monthly cash flow", `${money(d.cashflow)}/mo`],
                  ["IRR", pct(d.irr)],
                ]}
              />
            );
          }}
        />
        <Bar dataKey="cashflow" maxBarSize={56} radius={[3, 3, 0, 0]}>
          {data.map((d) => (
            <Cell key={d.name} fill={d.cashflow < 0 ? BRICK : d.name === "Base" ? SLATE : WOOD} />
          ))}
        </Bar>
      </BarChart>
    </Frame>
  );
}
