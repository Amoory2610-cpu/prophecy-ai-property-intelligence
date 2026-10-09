"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { DemoBadge, EmptyState, ErrorState, LoadingRows, Notice, PageHeader, Section } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, ApiError, download } from "@/lib/api";
import { date, formatValue, money } from "@/lib/format";
import type { Comparison, PropertyPage, Unit } from "@/lib/types";
import { cn } from "@/lib/utils";

type Results = {
  comparison: Comparison;
  rows: (Record<string, unknown> & { property_id: string; title: string; is_demo: boolean; warnings: string[] })[];
  metrics: { key: string; label: string; unit: Unit; higher_is_better: boolean }[];
  leaders: Record<string, { best_property_id: string; worst_property_id: string }>;
  tradeoffs: string[];
  shared_assumptions: Record<string, unknown>;
  note: string;
};

const SHARED_FIELDS: [string, string, string][] = [
  ["interest_rate_pct", "Mortgage rate (%)", "5"],
  ["deposit_pct", "Deposit (%)", "25"],
  ["vacancy_pct", "Voids (% of year)", "4"],
  ["capital_growth_pct", "Capital growth (%/yr)", "3"],
  ["holding_years", "Holding period (years)", "10"],
];

export default function ComparePage() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const list = useQuery({ queryKey: ["comparisons"], queryFn: () => api<Comparison[]>("/comparisons") });
  const active = selected ?? list.data?.[0]?.id ?? null;

  return (
    <>
      <PageHeader
        title="Compare properties"
        description="Every property runs through the same financing, cost and growth assumptions, so differences come from the properties themselves."
      />
      <div className="grid gap-10 xl:grid-cols-[320px_1fr]">
        <aside className="space-y-8">
          <NewComparison
            onCreated={(id) => {
              qc.invalidateQueries({ queryKey: ["comparisons"] });
              setSelected(id);
            }}
          />
          {list.data && list.data.length > 0 && (
            <div>
              <h2 className="mb-2 text-sm font-semibold text-slate">Saved comparisons</h2>
              <ul>
                {list.data.map((c) => (
                  <li key={c.id}>
                    <button
                      type="button"
                      onClick={() => setSelected(c.id)}
                      aria-current={c.id === active}
                      className={cn(
                        "w-full border-b border-rule py-2 text-left text-sm hover:text-wood",
                        c.id === active && "font-semibold text-wood",
                      )}
                    >
                      {c.name}
                      <span className="block text-xs font-normal text-slate">
                        {c.property_ids.length} properties, updated {date(c.updated_at)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>
        <div className="min-w-0">
          {list.isLoading ? (
            <LoadingRows />
          ) : active ? (
            <ComparisonResults id={active} onDeleted={() => setSelected(null)} />
          ) : (
            <EmptyState title="Pick two or more properties to compare">
              Choose properties on the left. You can set the shared assumptions or use your defaults.
            </EmptyState>
          )}
        </div>
      </div>
    </>
  );
}

function NewComparison({ onCreated }: { onCreated: (id: string) => void }) {
  const props = useQuery({ queryKey: ["properties", "picker"], queryFn: () => api<PropertyPage>("/properties?page_size=100") });
  const [ids, setIds] = useState<string[]>([]);
  const [name, setName] = useState("");
  const [shared, setShared] = useState<Record<string, string>>({});
  const create = useMutation({
    mutationFn: () => {
      const assumptions = Object.fromEntries(
        Object.entries(shared)
          .filter(([, v]) => v.trim() !== "")
          .map(([k, v]) => [k, Number(v)]),
      );
      return api<Comparison>("/comparisons", {
        method: "POST",
        body: { name: name || `Comparison of ${ids.length} properties`, property_ids: ids, assumptions },
      });
    },
    onSuccess: (c) => {
      setIds([]);
      setName("");
      onCreated(c.id);
      toast.success("Comparison saved");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.summary : "Could not create the comparison"),
  });

  if (props.data && props.data.items.length < 2) {
    return (
      <Notice title="Add at least two properties first">
        <Link href="/properties/new" className="font-medium text-wood underline">
          Add a property
        </Link>
      </Notice>
    );
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate();
      }}
      className="rounded-xl border border-rule bg-card p-4"
    >
      <h2 className="font-heading text-base font-semibold">New comparison</h2>
      <p className="mt-0.5 text-xs text-slate">Choose 2 to 6 properties.</p>
      <div className="mt-3 max-h-60 space-y-1.5 overflow-y-auto pr-1">
        {props.data?.items.map((p) => {
          const checked = ids.includes(p.id);
          return (
            <label key={p.id} className="flex cursor-pointer items-start gap-2 text-sm">
              <Checkbox
                checked={checked}
                disabled={!checked && ids.length >= 6}
                onCheckedChange={(c) => setIds((x) => (c ? [...x, p.id] : x.filter((i) => i !== p.id)))}
                className="mt-0.5"
              />
              <span>
                {p.title}
                <span className="block text-xs text-slate">{money(p.asking_price)}</span>
              </span>
            </label>
          );
        })}
      </div>
      <div className="mt-4 space-y-2.5 border-t border-rule pt-3">
        <p className="text-xs text-slate">Shared assumptions (blank = your defaults)</p>
        {SHARED_FIELDS.map(([k, label, ph]) => (
          <div key={k} className="flex items-center justify-between gap-2">
            <Label htmlFor={`cmp-${k}`} className="text-xs font-normal">
              {label}
            </Label>
            <Input
              id={`cmp-${k}`}
              type="number"
              step="any"
              placeholder={ph}
              value={shared[k] ?? ""}
              onChange={(e) => setShared((s) => ({ ...s, [k]: e.target.value }))}
              className="num h-8 w-24 bg-card"
            />
          </div>
        ))}
        <Input aria-label="Comparison name" placeholder="Name (optional)" value={name} onChange={(e) => setName(e.target.value)} className="h-8 bg-card" />
      </div>
      <Button type="submit" className="mt-4 w-full" disabled={ids.length < 2 || create.isPending}>
        {create.isPending ? "Comparing…" : `Compare ${ids.length || ""} properties`}
      </Button>
    </form>
  );
}

function ComparisonResults({ id, onDeleted }: { id: string; onDeleted: () => void }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["comparison-results", id], queryFn: () => api<Results>(`/comparisons/${id}/results`) });
  const remove = useMutation({
    mutationFn: () => api(`/comparisons/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["comparisons"] });
      onDeleted();
    },
  });
  const exportCsv = useMutation({
    mutationFn: async () => {
      const r = await api<{ id: string; filename: string }>(`/comparisons/${id}/export`, { method: "POST" });
      await download(`/reports/${r.id}/download`, r.filename);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["reports"] });
      toast.success("CSV downloaded and saved to Reports");
    },
  });

  if (q.isLoading) return <LoadingRows rows={8} />;
  if (q.error) return <ErrorState error={q.error} retry={() => q.refetch()} />;
  const d = q.data!;
  const s = d.shared_assumptions;

  return (
    <Section
      title={d.comparison.name}
      description={`Shared: ${s.interest_rate_pct}% ${String(s.mortgage_type).replace("_", "-")} mortgage, ${s.deposit_pct}% deposit, ${s.vacancy_pct}% voids, ${s.capital_growth_pct}% growth over ${s.holding_years} years.`}
      aside={
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => exportCsv.mutate()} disabled={exportCsv.isPending}>
            Export CSV
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              if (confirm("Delete this comparison?")) remove.mutate();
            }}
          >
            Delete
          </Button>
        </div>
      }
    >
      <div className="overflow-x-auto rounded-xl border border-rule bg-card">
        <Table className="min-w-[640px] [&_td]:px-4 [&_th]:px-4">
          <TableHeader>
            <TableRow>
              <TableHead className="w-56">Measure</TableHead>
              {d.rows.map((r) => (
                <TableHead key={r.property_id} className="text-right align-bottom">
                  <Link href={`/properties/${r.property_id}`} className="font-semibold text-ink hover:underline">
                    {r.title}
                  </Link>
                  {r.is_demo && (
                    <span className="mt-1 flex justify-end">
                      <DemoBadge />
                    </span>
                  )}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell className="text-slate">Purchase price</TableCell>
              {d.rows.map((r) => (
                <TableCell key={r.property_id} className="num text-right">
                  {money(r.purchase_price as number)}
                </TableCell>
              ))}
            </TableRow>
            <TableRow>
              <TableCell className="text-slate">Rent per month</TableCell>
              {d.rows.map((r) => (
                <TableCell key={r.property_id} className="num text-right">
                  {money(r.monthly_rent as number)}
                </TableCell>
              ))}
            </TableRow>
            <TableRow>
              <TableCell className="text-slate">Transaction tax (est.)</TableCell>
              {d.rows.map((r) => (
                <TableCell key={r.property_id} className="num text-right">
                  {money(r.transaction_tax as number)}
                </TableCell>
              ))}
            </TableRow>
            {d.metrics.map((m) => (
              <TableRow key={m.key}>
                <TableCell>
                  {m.label}
                  <span className="block text-[11px] text-slate">{m.higher_is_better ? "higher is better" : "lower is better"}</span>
                </TableCell>
                {d.rows.map((r) => {
                  const lead = d.leaders[m.key];
                  const best = lead?.best_property_id === r.property_id;
                  const worst = lead?.worst_property_id === r.property_id;
                  return (
                    <TableCell
                      key={r.property_id}
                      className={cn("num text-right", best && "bg-wood-soft font-semibold text-wood", worst && "text-brick")}
                    >
                      {formatValue(r[m.key] as number | null, m.unit === "gbp_month" ? "gbp" : m.unit)}
                      {best && <span className="sr-only"> (best)</span>}
                      {worst && <span className="sr-only"> (weakest)</span>}
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="mt-2 text-xs text-slate">Green marks the strongest figure on each line and brick the weakest.</p>

      {d.tradeoffs.length > 0 && (
        <div className="mt-6">
          <h3 className="text-sm font-semibold text-slate">Trade-offs</h3>
          <ul className="mt-2 list-disc space-y-1.5 pl-4 text-sm leading-relaxed">
            {d.tradeoffs.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </div>
      )}
      <p className="mt-5 text-xs leading-relaxed text-slate">{d.note}</p>
    </Section>
  );
}
