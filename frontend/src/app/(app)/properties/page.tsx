"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { DemoBadge, EmptyState, ErrorState, LoadingRows, PageHeader } from "@/components/common";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { money, pct, PROPERTY_TYPES, REGIONS } from "@/lib/format";
import type { PropertyPage } from "@/lib/types";

const selectCls = "h-9 rounded-md border border-input bg-card px-2.5 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-ring/40";

export default function PropertiesPage() {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [region, setRegion] = useState("");
  const [type, setType] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [minYield, setMinYield] = useState("");
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const t = setTimeout(() => {
      setDebounced(q);
      setPage(1);
    }, 250);
    return () => clearTimeout(t);
  }, [q]);
  // Changing a filter returns to the first page.
  const filter = (set: (v: string) => void) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    set(e.target.value);
    setPage(1);
  };

  const params = new URLSearchParams({ sort, page: String(page), page_size: "20" });
  if (debounced) params.set("q", debounced);
  if (region) params.set("region", region);
  if (type) params.set("property_type", type);
  if (maxPrice) params.set("max_price", maxPrice);
  if (minYield) params.set("min_yield", minYield);

  const query = useQuery({
    queryKey: ["properties", params.toString()],
    queryFn: () => api<PropertyPage>(`/properties?${params}`),
    placeholderData: keepPreviousData,
  });
  const filtered = Boolean(debounced || region || type || maxPrice || minYield);
  const pages = query.data ? Math.max(1, Math.ceil(query.data.total / query.data.page_size)) : 1;

  return (
    <>
      <PageHeader
        title="Properties"
        description="Your shortlist. Gross yield here is simply annual rent divided by asking price; open a property for the full analysis."
        actions={
          <>
            <Link href="/properties/new" className={buttonVariants()}>
              Add a property
            </Link>
            <Link href="/data" className={buttonVariants({ variant: "outline" })}>
              Import CSV
            </Link>
          </>
        }
      />

      <div className="mb-5 flex flex-wrap items-end gap-3" role="search">
        <div className="relative min-w-56 flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-slate" aria-hidden />
          <Input aria-label="Search by name, town or postcode" placeholder="Search by name, town or postcode" value={q} onChange={(e) => setQ(e.target.value)} className="h-9 bg-card pl-8" />
        </div>
        <select aria-label="Nation" value={region} onChange={filter(setRegion)} className={selectCls}>
          <option value="">All nations</option>
          {Object.entries(REGIONS).map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
        <select aria-label="Property type" value={type} onChange={filter(setType)} className={selectCls}>
          <option value="">All types</option>
          {Object.entries(PROPERTY_TYPES).map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
        <Input aria-label="Maximum price" type="number" placeholder="Max price £" value={maxPrice} onChange={filter(setMaxPrice)} className="h-9 w-32 bg-card" />
        <Input aria-label="Minimum gross yield %" type="number" placeholder="Min yield %" value={minYield} onChange={filter(setMinYield)} className="h-9 w-28 bg-card" />
        <select aria-label="Sort" value={sort} onChange={filter(setSort)} className={selectCls}>
          <option value="newest">Newest first</option>
          <option value="yield_desc">Highest gross yield</option>
          <option value="price_asc">Lowest price</option>
          <option value="price_desc">Highest price</option>
          <option value="rent_desc">Highest rent</option>
        </select>
      </div>

      {query.isLoading && <LoadingRows />}
      {query.error && <ErrorState error={query.error} retry={() => query.refetch()} />}
      {query.data &&
        (query.data.items.length === 0 ? (
          filtered ? (
            <EmptyState title="No properties match these filters">Clear a filter or broaden the search.</EmptyState>
          ) : (
            <EmptyState title="No properties yet" action={{ href: "/properties/new", label: "Add a property" }}>
              Add one by hand, import a CSV from the data sources page, or load the demo portfolio from the dashboard.
            </EmptyState>
          )
        ) : (
          <>
            <div className="overflow-x-auto">
              <Table className="min-w-[720px]">
                <TableHeader>
                  <TableRow>
                    <TableHead>Property</TableHead>
                    <TableHead>Location</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead className="text-right">Asking price</TableHead>
                    <TableHead className="text-right">Rent /mo</TableHead>
                    <TableHead className="text-right">Gross yield</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {query.data.items.map((p) => (
                    <TableRow key={p.id}>
                      <TableCell>
                        <div className="flex flex-wrap items-center gap-2">
                          <Link href={`/properties/${p.id}`} className="font-medium text-ink hover:underline">
                            {p.title}
                          </Link>
                          {p.is_demo && <DemoBadge />}
                        </div>
                      </TableCell>
                      <TableCell className="text-slate">{[p.town, p.postcode].filter(Boolean).join(", ") || REGIONS[p.region]}</TableCell>
                      <TableCell className="text-slate">
                        {PROPERTY_TYPES[p.property_type]}
                        {p.bedrooms !== null && `, ${p.bedrooms} bed`}
                      </TableCell>
                      <TableCell className="num text-right">{money(p.asking_price)}</TableCell>
                      <TableCell className="num text-right">{money(p.estimated_monthly_rent)}</TableCell>
                      <TableCell className="num text-right font-medium">{pct(p.gross_yield_pct)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <div className="mt-4 flex items-center justify-between text-sm text-slate">
              <p>
                {query.data.total} {query.data.total === 1 ? "property" : "properties"}
              </p>
              {pages > 1 && (
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                    Previous
                  </Button>
                  <span>
                    Page {page} of {pages}
                  </span>
                  <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>
                    Next
                  </Button>
                </div>
              )}
            </div>
          </>
        ))}
    </>
  );
}
