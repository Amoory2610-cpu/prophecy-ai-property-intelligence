"use client";

import { useEffect, useState } from "react";

import { LedgerRow } from "@/components/ledger";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import type { Metric } from "@/lib/types";

type Preview = { metrics: Metric[]; assumptions: string };

export function QuickEstimate() {
  const [price, setPrice] = useState("195000");
  const [rent, setRent] = useState("1150");
  const [rate, setRate] = useState("5.0");
  const [data, setData] = useState<Preview | null>(null);
  const [fetchError, setError] = useState<string | null>(null);

  const p = Number(price.replace(/[£,\s]/g, ""));
  const r = Number(rent.replace(/[£,\s]/g, ""));
  const i = Number(rate);
  const valid = p > 0 && !Number.isNaN(r) && r >= 0 && !Number.isNaN(i);
  const error = valid ? fetchError : "Enter a price above zero, a rent of zero or more and an interest rate.";

  useEffect(() => {
    if (!valid) return;
    const t = setTimeout(() => {
      api<Preview>("/public/preview", {
        method: "POST",
        body: { purchase_price: p, monthly_rent: r, interest_rate_pct: i },
      })
        .then((d) => {
          setData(d);
          setError(null);
        })
        .catch((e) => setError(e instanceof ApiError ? e.summary : "Could not calculate."));
    }, 250);
    return () => clearTimeout(t);
  }, [p, r, i, valid]);

  return (
    <div className="rounded-2xl border border-rule bg-card p-5 shadow-[0_1px_0_var(--rule),0_12px_32px_-24px_rgba(22,33,44,0.35)] sm:p-6">
      <div className="grid grid-cols-3 gap-3">
        <div>
          <Label htmlFor="qe-price" className="text-xs text-slate">Purchase price (£)</Label>
          <Input id="qe-price" inputMode="numeric" value={price} onChange={(e) => setPrice(e.target.value)} className="num mt-1 bg-paper/50" />
        </div>
        <div>
          <Label htmlFor="qe-rent" className="text-xs text-slate">Rent per month (£)</Label>
          <Input id="qe-rent" inputMode="numeric" value={rent} onChange={(e) => setRent(e.target.value)} className="num mt-1 bg-paper/50" />
        </div>
        <div>
          <Label htmlFor="qe-rate" className="text-xs text-slate">Mortgage rate (%)</Label>
          <Input id="qe-rate" inputMode="decimal" value={rate} onChange={(e) => setRate(e.target.value)} className="num mt-1 bg-paper/50" />
        </div>
      </div>
      <div className="mt-4" aria-live="polite">
        {error ? (
          <p className="py-6 text-sm text-brick">{error}</p>
        ) : data ? (
          <>
            {data.metrics.map((m) => (
              <LedgerRow key={m.key} metric={m} emphasis={m.key === "monthly_cash_flow"} />
            ))}
            <p className="mt-3 text-xs leading-relaxed text-slate">
              Select any figure to see how it was worked out. {data.assumptions}
            </p>
          </>
        ) : (
          <p className="py-6 text-sm text-slate">Calculating…</p>
        )}
      </div>
    </div>
  );
}
