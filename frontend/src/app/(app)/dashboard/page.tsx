"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { toast } from "sonner";

import { EmptyState, ErrorState, Figure, LoadingRows, Notice, PageHeader, Section } from "@/components/common";
import { Button, buttonVariants } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import { compactMoney, date, dateTime, money, pct, signClass } from "@/lib/format";
import { useMe } from "@/lib/session";
import type { Coverage, Headline } from "@/lib/types";
import { cn } from "@/lib/utils";

type Dashboard = {
  counts: Record<"properties" | "demo_properties" | "analyses" | "comparisons" | "watchlists" | "reports", number>;
  portfolio: {
    total_asking_price: number;
    total_monthly_rent: number;
    average_gross_yield_pct: number | null;
    best_gross_yield_pct: number | null;
    analysed_properties: ({ property_id: string; title: string } & Headline)[];
  };
  recent_analyses: ({ id: string; name: string; property_id: string | null; created_at: string } & Headline)[];
  market_data: Coverage;
};

export default function DashboardPage() {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["dashboard"], queryFn: () => api<Dashboard>("/dashboard") });
  const loadDemo = useMutation({
    mutationFn: () => api("/properties/demo", { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries();
      toast.success("Demo portfolio added. Prices and rents in it are illustrative.");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.summary : "Could not add the demo portfolio"),
  });

  const greeting = me?.full_name ? `Welcome back, ${me.full_name.split(" ")[0]}` : "Your portfolio";

  return (
    <>
      <PageHeader
        title={greeting}
        description="Properties you're considering, your latest analyses and the market data behind them."
        actions={
          <>
            <Link href="/properties/new" className={buttonVariants()}>
              Add a property
            </Link>
            <Link href="/simulator" className={buttonVariants({ variant: "outline" })}>
              Open the simulator
            </Link>
          </>
        }
      />
      {q.isLoading && <LoadingRows rows={6} />}
      {q.error && <ErrorState error={q.error} retry={() => q.refetch()} />}
      {q.data && (
        <>
          {q.data.counts.properties === 0 ? (
            <EmptyState
              title="Start with a property you're looking at"
              action={
                <div className="flex flex-wrap justify-center gap-2">
                  <Link href="/properties/new" className={buttonVariants()}>
                    Add a property
                  </Link>
                  <Button variant="outline" onClick={() => loadDemo.mutate()} disabled={loadDemo.isPending}>
                    {loadDemo.isPending ? "Adding…" : "Load the demo portfolio"}
                  </Button>
                </div>
              }
            >
              Enter the asking price and the rent you expect, or import a CSV of your shortlist. The demo portfolio
              adds seven example properties with illustrative figures so you can explore first.
            </EmptyState>
          ) : (
            <div className="grid grid-cols-2 gap-x-6 gap-y-5 border-y border-rule py-5 md:grid-cols-4">
              <Figure
                label="Properties tracked"
                value={q.data.counts.properties}
                sub={q.data.counts.demo_properties ? `${q.data.counts.demo_properties} are demo data` : "All your own records"}
              />
              <Figure label="Combined asking prices" value={compactMoney(q.data.portfolio.total_asking_price)} />
              <Figure label="Combined expected rent" value={`${money(q.data.portfolio.total_monthly_rent)}/mo`} />
              <Figure
                label="Average gross yield"
                value={pct(q.data.portfolio.average_gross_yield_pct)}
                sub={`Highest ${pct(q.data.portfolio.best_gross_yield_pct)}`}
              />
            </div>
          )}

          <div className="mt-10 grid gap-10 xl:grid-cols-[1fr_340px]">
            <div className="min-w-0">
              <Section
                title="Analysed properties"
                description="Latest saved analysis for each property, on the assumptions used at the time."
                aside={
                  <Link href="/compare" className="text-sm font-medium text-wood underline underline-offset-2">
                    Compare properties
                  </Link>
                }
              >
                {q.data.portfolio.analysed_properties.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-input px-4 py-6 text-sm text-slate">
                    No analyses yet. Open a property and choose <strong className="text-ink">Run analysis</strong>.
                  </p>
                ) : (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Property</TableHead>
                          <TableHead className="text-right">Gross yield</TableHead>
                          <TableHead className="text-right">Cash flow /mo</TableHead>
                          <TableHead className="text-right">Cash-on-cash</TableHead>
                          <TableHead className="text-right">IRR (est.)</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {q.data.portfolio.analysed_properties.map((p) => (
                          <TableRow key={p.property_id}>
                            <TableCell>
                              <Link href={`/properties/${p.property_id}`} className="font-medium text-ink hover:underline">
                                {p.title}
                              </Link>
                            </TableCell>
                            <TableCell className="num text-right">{pct(p.gross_yield)}</TableCell>
                            <TableCell className={cn("num text-right", signClass(p.monthly_cash_flow))}>{money(p.monthly_cash_flow)}</TableCell>
                            <TableCell className="num text-right">{pct(p.cash_on_cash)}</TableCell>
                            <TableCell className="num text-right">{pct(p.irr)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </Section>

              <Section title="Recent analyses">
                {q.data.recent_analyses.length === 0 ? (
                  <p className="text-sm text-slate">Saved analyses will appear here.</p>
                ) : (
                  <ul>
                    {q.data.recent_analyses.map((a) => (
                      <li key={a.id} className="flex flex-wrap items-baseline gap-x-3 border-b border-rule py-2.5 text-sm">
                        <Link href={`/analyses/${a.id}`} className="font-medium text-ink hover:underline">
                          {a.name}
                        </Link>
                        <span className="text-xs text-slate">{dateTime(a.created_at)}</span>
                        <span className={cn("num ml-auto", signClass(a.monthly_cash_flow))}>{money(a.monthly_cash_flow)}/mo</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Section>
            </div>

            <aside className="space-y-6">
              <MarketCoverage c={q.data.market_data} />
              <div className="rounded-xl border border-rule bg-card p-5 text-sm">
                <h2 className="font-heading text-base font-semibold">Saved work</h2>
                <dl className="mt-3 space-y-1.5">
                  {[
                    ["Analyses", q.data.counts.analyses, "/properties"],
                    ["Comparisons", q.data.counts.comparisons, "/compare"],
                    ["Watchlists", q.data.counts.watchlists, "/watchlists"],
                    ["Reports", q.data.counts.reports, "/reports"],
                  ].map(([label, n, href]) => (
                    <div key={label as string} className="flex items-baseline gap-2">
                      <dt>
                        <Link href={href as string} className="hover:underline">
                          {label}
                        </Link>
                      </dt>
                      <span className="leader" aria-hidden />
                      <dd className="num font-medium">{n}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            </aside>
          </div>
        </>
      )}
    </>
  );
}

function MarketCoverage({ c }: { c: Coverage }) {
  if (!c.transactions) {
    return (
      <Notice title="No market data imported">
        Comparable sales and area statistics need HM Land Registry Price Paid Data.{" "}
        <Link href="/data" className="font-medium text-wood underline underline-offset-2">
          See data sources
        </Link>
      </Notice>
    );
  }
  return (
    <div className="rounded-xl border border-rule bg-card p-5 text-sm">
      <h2 className="font-heading text-base font-semibold">Market data</h2>
      <p className="num mt-2 text-2xl font-semibold">{c.transactions.toLocaleString("en-GB")}</p>
      <p className="text-slate">recorded sales in England and Wales</p>
      <dl className="mt-3 space-y-1 text-xs text-slate">
        <div className="flex justify-between gap-2">
          <dt>Covers</dt>
          <dd className="num text-ink">
            {date(c.earliest_transaction)} to {date(c.latest_transaction)}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Imported</dt>
          <dd className="num text-ink">{dateTime(c.last_imported_at)}</dd>
        </div>
      </dl>
      {c.days_since_latest_transaction !== null && c.days_since_latest_transaction > 120 && (
        <p className="mt-3 rounded-md bg-ochre-soft px-2.5 py-2 text-xs text-ochre">
          The newest sale is {c.days_since_latest_transaction} days old. Import a newer Land Registry file for current prices.
        </p>
      )}
      <p className="mt-3 text-[11px] leading-relaxed text-slate">{c.attribution}</p>
    </div>
  );
}
