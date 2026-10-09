"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";

import { HistogramChart, TrendChart } from "@/components/charts";
import { ErrorState, Figure, LoadingRows, Notice, PageHeader, Panel, Section } from "@/components/common";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { date, dateTime, money, pct } from "@/lib/format";
import type { Coverage, PriceStats } from "@/lib/types";
import { cn } from "@/lib/utils";

type Area = { kind: string; value: string; label: string; transactions?: number };
type Summary = {
  area: Area;
  available: boolean;
  message?: string;
  period: { from: string; to: string; months: number };
  overall: PriceStats;
  by_property_type: ({ property_type: string; label: string } & PriceStats)[];
  new_build_share_pct: number | null;
  leasehold_share_pct: number | null;
  histogram: { from: number; to: number; count: number }[];
  method: string;
};
type Trend = { points: { month: string; median: number | null; count: number; low_sample: boolean }[]; note: string };
type Score = { predicted: number; coverage_pct: number; median_ape_pct: number | null; mean_ape_pct: number | null; within_10_pct: number | null; within_20_pct: number | null };
type Evaluation =
  | { available: false; message: string }
  | {
      available: true;
      method: string;
      train_period: { from: string; to: string; sales: number };
      test_period: { from: string; to: string; sales: number };
      model: Score;
      baseline: Score & { description: string };
      interpretation: string;
    };

const TYPES: [string, string][] = [["", "All types"], ["D", "Detached"], ["S", "Semi-detached"], ["T", "Terraced"], ["F", "Flats"], ["O", "Other"]];
const KIND_LABEL: Record<string, string> = { local_authority: "Local authority", town: "Town", district: "Postcode district", sector: "Postcode sector" };

export default function MarketPage() {
  const coverage = useQuery({ queryKey: ["coverage"], queryFn: () => api<Coverage>("/market/coverage") });
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [area, setArea] = useState("Leeds");
  const [type, setType] = useState("");
  const [months, setMonths] = useState("12");

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query), 250);
    return () => clearTimeout(t);
  }, [query]);

  const suggestions = useQuery({
    queryKey: ["areas", debounced],
    queryFn: () => api<Area[]>(`/market/areas?q=${encodeURIComponent(debounced)}`),
    enabled: debounced.trim().length >= 2,
  });
  const hasData = (coverage.data?.transactions ?? 0) > 0;
  const qs = `area=${encodeURIComponent(area)}${type ? `&property_type=${type}` : ""}`;
  const summary = useQuery({
    queryKey: ["market-summary", qs, months],
    queryFn: () => api<Summary>(`/market/summary?${qs}&months=${months}`),
    enabled: hasData && Boolean(area),
  });
  const trend = useQuery({ queryKey: ["market-trend", qs], queryFn: () => api<Trend>(`/market/trend?${qs}`), enabled: hasData && Boolean(area) });
  const evaluation = useQuery({ queryKey: ["model-eval"], queryFn: () => api<Evaluation>("/market/model-evaluation"), enabled: hasData, staleTime: 10 * 60_000 });

  return (
    <>
      <PageHeader
        title="Market data"
        description="Recorded sale prices from HM Land Registry for England and Wales. Rents are not included: this data covers sales only."
      />
      {coverage.isLoading && <LoadingRows />}
      {coverage.data && !hasData && (
        <Notice title="No Land Registry data has been imported">
          Market analytics are computed only from imported HM Land Registry Price Paid Data; nothing is estimated or invented here.{" "}
          <Link href="/data" className="font-medium text-wood underline underline-offset-2">
            See how to import it
          </Link>
          .
        </Notice>
      )}

      {hasData && coverage.data && (
        <>
          <div className="mb-8 flex flex-wrap items-center gap-x-6 gap-y-1 rounded-lg border border-rule bg-card px-4 py-3 text-xs text-slate">
            <span>
              <strong className="num text-ink">{coverage.data.transactions.toLocaleString("en-GB")}</strong> sales from{" "}
              {date(coverage.data.earliest_transaction)} to {date(coverage.data.latest_transaction)}
            </span>
            <span>Imported {dateTime(coverage.data.last_imported_at)}</span>
            {coverage.data.days_since_latest_transaction !== null && coverage.data.days_since_latest_transaction > 120 && (
              <span className="rounded-sm bg-ochre-soft px-1.5 py-px font-medium text-ochre">
                Newest sale is {coverage.data.days_since_latest_transaction} days old
              </span>
            )}
          </div>

          <div className="mb-8 flex flex-wrap items-end gap-3">
            <div className="relative w-80 max-w-full">
              <label htmlFor="area-q" className="text-[13px] text-slate">
                Area: town, local authority or postcode district
              </label>
              <Input
                id="area-q"
                placeholder="Try Manchester, LS6 or CF24 2"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && query.trim()) {
                    setArea(query.trim());
                    setQuery("");
                  }
                }}
                className="mt-1 h-9 bg-card"
                autoComplete="off"
                role="combobox"
                aria-expanded={Boolean(suggestions.data?.length && query)}
                aria-controls="area-list"
              />
              {query && suggestions.data && suggestions.data.length > 0 && (
                <ul id="area-list" role="listbox" className="absolute z-20 mt-1 w-full overflow-hidden rounded-md border border-rule bg-card shadow-md">
                  {suggestions.data.map((s) => (
                    <li key={`${s.kind}-${s.value}`} role="option" aria-selected={false}>
                      <button
                        type="button"
                        className="flex w-full justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-muted"
                        onClick={() => {
                          setArea(s.value);
                          setQuery("");
                        }}
                      >
                        <span>{s.label}</span>
                        <span className="text-xs text-slate">
                          {KIND_LABEL[s.kind]}
                          {s.transactions ? `, ${s.transactions.toLocaleString("en-GB")} sales` : ""}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <select aria-label="Property type" value={type} onChange={(e) => setType(e.target.value)} className="h-9 rounded-md border border-input bg-card px-2.5 text-sm">
              {TYPES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
            <select aria-label="Period" value={months} onChange={(e) => setMonths(e.target.value)} className="h-9 rounded-md border border-input bg-card px-2.5 text-sm">
              {[["3", "Last 3 months"], ["6", "Last 6 months"], ["12", "Last 12 months"], ["36", "Last 3 years"]].map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </div>

          {summary.error && <ErrorState error={summary.error} />}
          {summary.isLoading && <LoadingRows rows={6} />}
          {summary.data && summary.data.available && (
            <>
              <h2 className="mb-3 text-2xl font-semibold">{summary.data.area.label}</h2>
              <div className="grid grid-cols-2 gap-x-6 gap-y-5 border-y border-rule py-5 md:grid-cols-4">
                <Figure label="Median sale price" value={money(summary.data.overall.median)} sub={`${summary.data.overall.count.toLocaleString("en-GB")} sales`} />
                <Figure label="Middle half of sales" value={`${money(summary.data.overall.p25)} to ${money(summary.data.overall.p75)}`} sub="25th to 75th percentile" />
                <Figure label="New builds" value={pct(summary.data.new_build_share_pct, 1)} sub="Share of sales" />
                <Figure label="Leasehold" value={pct(summary.data.leasehold_share_pct, 1)} sub="Share of sales" />
              </div>
              {summary.data.overall.low_sample && (
                <Notice tone="warn" className="mt-4">
                  Fewer than 10 sales match. Treat these figures as indicative only.
                </Notice>
              )}
              <p className="mt-2 text-xs text-slate">
                {date(summary.data.period.from)} to {date(summary.data.period.to)}. {summary.data.method}
              </p>

              <div className="mt-10 grid gap-10 lg:grid-cols-2">
                <Section title="Monthly median price" description={trend.data?.note}>
                  <Panel>{trend.data ? <TrendChart points={trend.data.points} /> : <LoadingRows rows={4} />}</Panel>
                  <p className="mt-2 text-xs text-slate">Hollow points mark months with fewer than 10 sales. Grey bars show the number of sales.</p>
                </Section>
                <Section title="Price distribution" description="Sales in the selected period, excluding the top 2% so the shape stays readable.">
                  <Panel>
                    <HistogramChart bins={summary.data.histogram} />
                  </Panel>
                </Section>
              </div>

              <Section title="By property type">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Type</TableHead>
                      <TableHead className="text-right">Sales</TableHead>
                      <TableHead className="text-right">Median</TableHead>
                      <TableHead className="text-right">25th percentile</TableHead>
                      <TableHead className="text-right">75th percentile</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {summary.data.by_property_type.map((t) => (
                      <TableRow key={t.property_type}>
                        <TableCell>
                          {t.label}
                          {t.low_sample && <span className="ml-2 text-xs text-ochre">small sample</span>}
                        </TableCell>
                        <TableCell className="num text-right">{t.count.toLocaleString("en-GB")}</TableCell>
                        <TableCell className="num text-right font-medium">{money(t.median)}</TableCell>
                        <TableCell className="num text-right">{money(t.p25)}</TableCell>
                        <TableCell className="num text-right">{money(t.p75)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Section>
            </>
          )}

          <Section
            title="How reliable is the comparable-sales estimate?"
            description="A live backtest on the imported data: the most recent three months are held out and each sale is predicted from earlier sales nearby."
          >
            {evaluation.isLoading && <LoadingRows rows={3} />}
            {evaluation.data && !evaluation.data.available && <Notice>{evaluation.data.message}</Notice>}
            {evaluation.data && evaluation.data.available && <EvaluationTable e={evaluation.data} />}
          </Section>

          <p className="border-t border-rule pt-4 text-xs leading-relaxed text-slate">
            {coverage.data.attribution}{" "}
            <a href={coverage.data.source_url} target="_blank" rel="noreferrer" className="underline">
              Source
            </a>
          </p>
        </>
      )}
    </>
  );
}

function EvaluationTable({ e }: { e: Extract<Evaluation, { available: true }> }) {
  const rows: [string, (s: Score) => string][] = [
    ["Median error", (s) => pct(s.median_ape_pct, 1)],
    ["Average error", (s) => pct(s.mean_ape_pct, 1)],
    ["Within 10% of the actual price", (s) => pct(s.within_10_pct, 1)],
    ["Within 20% of the actual price", (s) => pct(s.within_20_pct, 1)],
    ["Sales it could estimate", (s) => pct(s.coverage_pct, 1)],
  ];
  return (
    <>
      <div className="overflow-x-auto">
        <Table className="min-w-[520px]">
          <TableHeader>
            <TableRow>
              <TableHead>Measure</TableHead>
              <TableHead className="text-right">Comparables method</TableHead>
              <TableHead className="text-right">Baseline: district median</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map(([label, f]) => (
              <TableRow key={label}>
                <TableCell>{label}</TableCell>
                <TableCell className={cn("num text-right font-semibold")}>{f(e.model)}</TableCell>
                <TableCell className="num text-right text-slate">{f(e.baseline)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="mt-3 max-w-3xl text-xs leading-relaxed text-slate">
        Trained on {e.train_period.sales.toLocaleString("en-GB")} sales ({date(e.train_period.from)} to {date(e.train_period.to)}), tested on{" "}
        {e.test_period.sales.toLocaleString("en-GB")} later sales ({date(e.test_period.from)} to {date(e.test_period.to)}). {e.interpretation} An
        area median is a reference point, not a valuation.
      </p>
    </>
  );
}
