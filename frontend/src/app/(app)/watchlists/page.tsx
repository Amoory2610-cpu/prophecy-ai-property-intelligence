"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { DemoBadge, EmptyState, ErrorState, LoadingRows, PageHeader, Section } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import { date, money, pct } from "@/lib/format";
import type { Watchlist } from "@/lib/types";

export default function WatchlistsPage() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["watchlists"], queryFn: () => api<Watchlist[]>("/watchlists") });
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const create = useMutation({
    mutationFn: () => api("/watchlists", { method: "POST", body: { name, description } }),
    onSuccess: () => {
      setName("");
      setDescription("");
      qc.invalidateQueries({ queryKey: ["watchlists"] });
      toast.success("Watchlist created");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.summary : "Could not create the watchlist"),
  });
  const removeItem = useMutation({
    mutationFn: ({ wid, pid }: { wid: string; pid: string }) => api(`/watchlists/${wid}/items/${pid}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlists"] }),
  });
  const removeList = useMutation({
    mutationFn: (wid: string) => api(`/watchlists/${wid}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlists"] }),
  });

  return (
    <>
      <PageHeader title="Watchlists" description="Group properties you're tracking, for example by area or by stage of your search." />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) create.mutate();
        }}
        className="mb-10 flex flex-wrap items-end gap-3"
      >
        <Input aria-label="Watchlist name" placeholder="New list name, e.g. Leeds terraces" value={name} onChange={(e) => setName(e.target.value)} className="h-9 w-72 bg-card" />
        <Input aria-label="Description" placeholder="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} className="h-9 min-w-56 flex-1 bg-card" />
        <Button type="submit" disabled={!name.trim() || create.isPending}>
          Create watchlist
        </Button>
      </form>

      {q.isLoading && <LoadingRows />}
      {q.error && <ErrorState error={q.error} retry={() => q.refetch()} />}
      {q.data?.length === 0 && (
        <EmptyState title="No watchlists yet">
          Create a list above, then use <strong className="text-ink">Add to watchlist</strong> on any property page.
        </EmptyState>
      )}
      {q.data?.map((w) => (
        <Section
          key={w.id}
          title={w.name}
          description={w.description || `Created ${date(w.created_at)}`}
          aside={
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                if (confirm(`Delete the watchlist "${w.name}"? The properties themselves are kept.`)) removeList.mutate(w.id);
              }}
            >
              Delete list
            </Button>
          }
        >
          {w.items.length === 0 ? (
            <p className="text-sm text-slate">Empty. Add properties from their detail pages.</p>
          ) : (
            <div className="overflow-x-auto">
              <Table className="min-w-[560px]">
                <TableHeader>
                  <TableRow>
                    <TableHead>Property</TableHead>
                    <TableHead>Added</TableHead>
                    <TableHead className="text-right">Asking price</TableHead>
                    <TableHead className="text-right">Gross yield</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {w.items.map((i) => (
                    <TableRow key={i.id}>
                      <TableCell>
                        <Link href={`/properties/${i.property_id}`} className="font-medium hover:underline">
                          {i.property.title}
                        </Link>{" "}
                        {i.property.is_demo && <DemoBadge />}
                      </TableCell>
                      <TableCell className="text-slate">{date(i.added_at)}</TableCell>
                      <TableCell className="num text-right">{money(i.property.asking_price)}</TableCell>
                      <TableCell className="num text-right">{pct(i.property.gross_yield_pct)}</TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="xs" onClick={() => removeItem.mutate({ wid: w.id, pid: i.property_id })}>
                          Remove
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </Section>
      ))}
    </>
  );
}
