"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { ErrorState, Figure, LoadingRows, Notice, PageHeader, Section, SourceBadge } from "@/components/common";
import { draftFrom, payloadFrom, PropertyForm } from "@/components/property-form";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import { date, dateTime, money, pct, PROPERTY_TYPES, REGIONS, RENT_SOURCES, signClass } from "@/lib/format";
import type { Analysis, Comparables, Property, Valuation, Watchlist } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function PropertyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [runOpen, setRunOpen] = useState(false);

  const prop = useQuery({ queryKey: ["property", id], queryFn: () => api<Property>(`/properties/${id}`) });
  const marketQ = useQuery({
    queryKey: ["property-market", id],
    queryFn: () => api<{ comparables: Comparables; valuation: Valuation | null; coverage_note: string | null }>(`/properties/${id}/market`),
    enabled: prop.isSuccess,
  });
  const analyses = useQuery({ queryKey: ["property-analyses", id], queryFn: () => api<Analysis[]>(`/properties/${id}/analyses`), enabled: prop.isSuccess });

  const remove = useMutation({
    mutationFn: () => api(`/properties/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries();
      toast.success("Property deleted");
      router.push("/properties");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.summary : "Could not delete"),
  });

  if (prop.isLoading) return <LoadingRows rows={8} />;
  if (prop.error) return <ErrorState error={prop.error} retry={() => prop.refetch()} />;
  const p = prop.data!;

  return (
    <>
      <PageHeader
        title={p.title}
        description={
          <span className="flex flex-wrap items-center gap-2">
            {[p.address_line, p.town, p.postcode].filter(Boolean).join(", ") || REGIONS[p.region]}
            <SourceBadge source={p.data_source} />
          </span>
        }
        actions={
          <>
            <Button onClick={() => setRunOpen(true)}>Run analysis</Button>
            <Button variant="outline" onClick={() => setEditing((e) => !e)}>
              {editing ? "Close editor" : "Edit details"}
            </Button>
            <WatchlistButton propertyId={p.id} />
            <Button
              variant="destructive"
              onClick={() => {
                if (confirm(`Delete "${p.title}" and its saved analyses? This can't be undone.`)) remove.mutate();
              }}
            >
              Delete
            </Button>
          </>
        }
      />

      {p.is_demo && (
        <Notice tone="warn" title="Demonstration property" className="mb-8">
          The asking price and rent are illustrative figures for exploring the product, not a real listing or market evidence.
          Comparable sales below are real HM Land Registry records for the postcode area.
        </Notice>
      )}

      {editing ? (
        <Section title="Edit details">
          <PropertyForm
            initial={draftFrom(p)}
            isDemo={p.is_demo}
            submitLabel="Save changes"
            onSubmit={async (d) => {
              await api(`/properties/${id}`, { method: "PATCH", body: payloadFrom(d, p.assumption_overrides) });
              await qc.invalidateQueries();
              toast.success("Changes saved");
              setEditing(false);
            }}
          />
        </Section>
      ) : (
        <div className="grid grid-cols-2 gap-x-6 gap-y-5 border-y border-rule py-5 md:grid-cols-4">
          <Figure label="Asking price" value={money(p.asking_price)} sub={`${PROPERTY_TYPES[p.property_type]}, ${p.tenure.replace(/_/g, " ")}`} />
          <Figure label="Expected rent" value={`${money(p.estimated_monthly_rent)}/mo`} sub={RENT_SOURCES[p.rent_source] ?? p.rent_source} />
          <Figure label="Gross yield" value={pct(p.gross_yield_pct)} sub="Rent × 12 ÷ asking price" />
          <Figure
            label="Size"
            value={p.bedrooms !== null ? `${p.bedrooms} bed` : "n/a"}
            sub={[p.bathrooms !== null && `${p.bathrooms} bath`, p.floor_area_sqm && `${p.floor_area_sqm} m²`].filter(Boolean).join(", ") || undefined}
          />
        </div>
      )}

      <div className="mt-10 grid gap-10 xl:grid-cols-[1fr_380px]">
        <div className="min-w-0">
          <Section title="Comparable sales" description="Recorded sale prices from HM Land Registry for the same postcode area and property type.">
            {marketQ.isLoading && <LoadingRows rows={4} />}
            {marketQ.error && <ErrorState error={marketQ.error} />}
            {marketQ.data && <ComparablesBlock data={marketQ.data} asking={p.asking_price} />}
          </Section>
        </div>
        <aside>
          <Section title="Saved analyses">
            {analyses.data?.length ? (
              <ul>
                {analyses.data.map((a) => (
                  <li key={a.id} className="border-b border-rule py-2.5">
                    <Link href={`/analyses/${a.id}`} className="text-sm font-medium text-ink hover:underline">
                      {a.name}
                    </Link>
                    <p className="num mt-0.5 flex justify-between text-xs text-slate">
                      <span>{dateTime(a.created_at)}</span>
                      <span className={signClass(a.headline.monthly_cash_flow)}>{money(a.headline.monthly_cash_flow)}/mo</span>
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate">
                No analyses yet. <strong className="text-ink">Run analysis</strong> applies your default assumptions, which you can
                change for this run.
              </p>
            )}
          </Section>
          {p.notes && (
            <Section title="Notes">
              <p className="whitespace-pre-line text-sm leading-relaxed text-slate">{p.notes}</p>
            </Section>
          )}
          {p.listing_url && (
            <a href={p.listing_url} target="_blank" rel="noreferrer noopener" className="text-sm font-medium text-wood underline underline-offset-2">
              Open the listing
            </a>
          )}
        </aside>
      </div>

      <RunAnalysisDialog property={p} open={runOpen} onOpenChange={setRunOpen} />
    </>
  );
}

function ComparablesBlock({
  data,
  asking,
}: {
  data: { comparables: Comparables; valuation: Valuation | null; coverage_note: string | null };
  asking: number;
}) {
  const { comparables: c, valuation: v } = data;
  if (data.coverage_note) return <Notice>{data.coverage_note}</Notice>;
  if (!c.available) {
    return (
      <Notice title="No comparable sales available">
        {c.message}{" "}
        <Link href="/data" className="font-medium text-wood underline underline-offset-2">
          Import Land Registry data
        </Link>
      </Notice>
    );
  }
  return (
    <>
      {v && (
        <div className="mb-5 rounded-xl border border-rule bg-card p-5">
          <div className="flex flex-wrap items-end gap-x-10 gap-y-4">
            <Figure label="Area median (reference point)" value={money(v.estimate)} sub={`Middle half: ${money(v.range_low)} to ${money(v.range_high)}`} />
            <Figure
              label="Asking price versus median"
              value={`${v.asking_vs_median_pct > 0 ? "+" : ""}${v.asking_vs_median_pct}%`}
              sub={`Asking ${money(asking)}`}
            />
            <Figure label="Based on" value={`${v.sample_size} sales`} sub={`${v.confidence} confidence`} />
          </div>
          <p className="mt-4 text-xs leading-relaxed text-slate">{v.method}</p>
          <ul className="mt-1.5 list-disc space-y-0.5 pl-4 text-xs text-slate">
            {v.limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="overflow-x-auto">
        <Table className="min-w-[620px]">
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Address</TableHead>
              <TableHead>Type</TableHead>
              <TableHead className="text-right">Price</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {c.sales!.map((s, i) => (
              <TableRow key={i}>
                <TableCell className="num whitespace-nowrap">{date(s.date)}</TableCell>
                <TableCell>
                  <span className="capitalize">{s.address.toLowerCase()}</span>
                  <span className="text-slate">, {s.postcode}</span>
                </TableCell>
                <TableCell className="text-slate">
                  {s.property_type}, {s.tenure.toLowerCase()}
                  {s.new_build && ", new build"}
                </TableCell>
                <TableCell className="num text-right font-medium">{money(s.price)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="mt-3 text-[11px] text-slate">
        Source: HM Land Registry Price Paid Data, postcode {c.level} {c.area}, {date(c.period?.from)} to {date(c.period?.to)}. Contains HM Land Registry
        data © Crown copyright and database right, licensed under the Open Government Licence v3.0.
      </p>
    </>
  );
}

function WatchlistButton({ propertyId }: { propertyId: string }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const lists = useQuery({ queryKey: ["watchlists"], queryFn: () => api<Watchlist[]>("/watchlists"), enabled: open });
  const add = useMutation({
    mutationFn: (wid: string) => api(`/watchlists/${wid}/items`, { method: "POST", body: { property_id: propertyId } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlists"] });
      toast.success("Added to watchlist");
      setOpen(false);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.summary : "Could not add"),
  });
  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)}>
        Add to watchlist
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add to a watchlist</DialogTitle>
            <DialogDescription>Choose a list. You can create lists on the Watchlists page.</DialogDescription>
          </DialogHeader>
          {lists.data?.length ? (
            <div className="space-y-1">
              {lists.data.map((w) => {
                const already = w.items.some((i) => i.property_id === propertyId);
                return (
                  <button
                    key={w.id}
                    type="button"
                    disabled={already || add.isPending}
                    onClick={() => add.mutate(w.id)}
                    className="flex w-full items-center justify-between rounded-md border border-rule px-3 py-2 text-left text-sm hover:bg-muted disabled:opacity-60"
                  >
                    <span className="font-medium">{w.name}</span>
                    <span className="text-xs text-slate">{already ? "Already on this list" : `${w.items.length} properties`}</span>
                  </button>
                );
              })}
            </div>
          ) : (
            <p className="text-sm text-slate">
              {lists.isLoading ? "Loading…" : (
                <>
                  You have no watchlists yet.{" "}
                  <Link href="/watchlists" className="font-medium text-wood underline">
                    Create one
                  </Link>
                </>
              )}
            </p>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

function RunAnalysisDialog({ property, open, onOpenChange }: { property: Property; open: boolean; onOpenChange: (o: boolean) => void }) {
  const router = useRouter();
  const qc = useQueryClient();
  const [price, setPrice] = useState(String(property.asking_price));
  const [rent, setRent] = useState(String(property.estimated_monthly_rent));
  const [rate, setRate] = useState("");
  const [deposit, setDeposit] = useState("");
  const [name, setName] = useState("");
  const run = useMutation({
    mutationFn: () => {
      const overrides: Record<string, number> = {};
      if (Number(price) !== property.asking_price) overrides.purchase_price = Number(price);
      if (Number(rent) !== property.estimated_monthly_rent) overrides.monthly_rent = Number(rent);
      if (rate) overrides.interest_rate_pct = Number(rate);
      if (deposit) overrides.deposit_pct = Number(deposit);
      return api<Analysis>(`/properties/${property.id}/analyses`, {
        method: "POST",
        body: { name: name || undefined, overrides },
      });
    },
    onSuccess: (a) => {
      qc.invalidateQueries();
      onOpenChange(false);
      router.push(`/analyses/${a.id}`);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.summary : "Could not run the analysis"),
  });
  const fields: [string, string, string, (v: string) => void, string][] = [
    ["ra-price", "Offer price (£)", price, setPrice, ""],
    ["ra-rent", "Monthly rent (£)", rent, setRent, ""],
    ["ra-rate", "Mortgage rate (%)", rate, setRate, "Your default"],
    ["ra-deposit", "Deposit (%)", deposit, setDeposit, "Your default"],
  ];
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Run analysis</DialogTitle>
          <DialogDescription>
            Uses your default assumptions from Account settings. Change anything here for this run only.
          </DialogDescription>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            run.mutate();
          }}
          className="space-y-4"
        >
          <div className="grid grid-cols-2 gap-3">
            {fields.map(([fid, label, value, set, ph]) => (
              <div key={fid}>
                <Label htmlFor={fid} className="text-[13px] text-slate">
                  {label}
                </Label>
                <Input id={fid} type="number" step="any" value={value} placeholder={ph} onChange={(e) => set(e.target.value)} className={cn("num mt-1 bg-card")} />
              </div>
            ))}
            <div className="col-span-2">
              <Label htmlFor="ra-name" className="text-[13px] text-slate">
                Name this analysis (optional)
              </Label>
              <Input id="ra-name" value={name} placeholder={`${property.title} analysis`} onChange={(e) => setName(e.target.value)} className="mt-1 bg-card" />
            </div>
          </div>
          <DialogFooter>
            <Button type="submit" disabled={run.isPending}>
              {run.isPending ? "Running…" : "Run analysis"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
