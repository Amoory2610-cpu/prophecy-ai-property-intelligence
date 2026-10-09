"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { AnalysisBody, HeadlineFigures, Warnings } from "@/components/analysis-view";
import { AssumptionsForm, errorsByField } from "@/components/assumptions-form";
import { Notice, PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { api, ApiError } from "@/lib/api";
import { money, pct } from "@/lib/format";
import type { Analysis, DealInputs, DealResults, PropertyPage } from "@/lib/types";

const QUICK: { key: keyof DealInputs; label: string; min: number; max: number; step: number; fmt: (v: number) => string }[] = [
  { key: "purchase_price", label: "Purchase price", min: 50_000, max: 1_000_000, step: 5_000, fmt: (v) => money(v) },
  { key: "monthly_rent", label: "Monthly rent", min: 300, max: 5_000, step: 25, fmt: (v) => money(v) },
  { key: "deposit_pct", label: "Deposit", min: 0, max: 100, step: 1, fmt: (v) => `${v}%` },
  { key: "interest_rate_pct", label: "Mortgage rate", min: 0, max: 12, step: 0.05, fmt: (v) => pct(v) },
  { key: "vacancy_pct", label: "Voids", min: 0, max: 30, step: 0.5, fmt: (v) => `${v}% of year` },
  { key: "maintenance_pct", label: "Maintenance", min: 0, max: 20, step: 0.5, fmt: (v) => `${v}% of rent` },
  { key: "holding_years", label: "Holding period", min: 1, max: 30, step: 1, fmt: (v) => `${v} years` },
];

export default function SimulatorPage() {
  const router = useRouter();
  const defaults = useQuery({
    queryKey: ["assumptions"],
    queryFn: () => api<{ effective: Partial<DealInputs> }>("/assumptions"),
  });
  const props = useQuery({ queryKey: ["properties", "picker"], queryFn: () => api<PropertyPage>("/properties?page_size=100") });
  const [edited, setEdited] = useState<Partial<DealInputs> | null>(null);
  const [result, setResult] = useState<DealResults | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [showAll, setShowAll] = useState(false);
  const seq = useRef(0);

  // Start from the user's default assumptions until they change something.
  const inputs: Partial<DealInputs> | null =
    edited ?? (defaults.data ? { purchase_price: 200_000, monthly_rent: 1_100, ...defaults.data.effective } : null);
  const setInputs = (f: (x: Partial<DealInputs> | null) => Partial<DealInputs>) => setEdited(f(inputs));

  // Recalculate as inputs change (debounced; stale responses are ignored).
  const payload = inputs ? JSON.stringify(inputs) : null;
  useEffect(() => {
    if (!payload) return;
    const n = ++seq.current;
    const t = setTimeout(() => {
      api<DealResults>("/calculate", { method: "POST", body: JSON.parse(payload) })
        .then((r) => {
          if (n === seq.current) {
            setResult(r);
            setError(null);
          }
        })
        .catch((e) => n === seq.current && setError(e instanceof ApiError ? e : new ApiError(0, "Calculation failed")));
    }, 200);
    return () => clearTimeout(t);
  }, [payload]);

  const save = useMutation({
    mutationFn: () => api<Analysis>("/analyses", { method: "POST", body: { name: "Simulator scenario", inputs } }),
    onSuccess: (a) => {
      toast.success("Scenario saved");
      router.push(`/analyses/${a.id}`);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.summary : "Could not save"),
  });

  const set = (key: keyof DealInputs, value: unknown) => setInputs((x) => ({ ...x, [key]: value }));

  return (
    <>
      <PageHeader
        title="Scenario simulator"
        description="Move the levers and every figure recalculates. Start from scratch or load one of your properties."
        actions={
          <>
            <select
              aria-label="Load a property"
              className="h-8 rounded-md border border-input bg-card px-2.5 text-sm"
              defaultValue=""
              onChange={(e) => {
                const p = props.data?.items.find((x) => x.id === e.target.value);
                if (p) {
                  setInputs((x) => ({
                    ...x,
                    purchase_price: p.asking_price,
                    monthly_rent: p.estimated_monthly_rent,
                    region: p.region,
                    ...(p.assumption_overrides as Partial<DealInputs>),
                  }));
                  toast.message(`Loaded ${p.title}${p.is_demo ? " (demo figures)" : ""}`);
                }
              }}
            >
              <option value="" disabled>
                Load a property…
              </option>
              {props.data?.items.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title}
                </option>
              ))}
            </select>
            <Button onClick={() => save.mutate()} disabled={!result || save.isPending}>
              Save as analysis
            </Button>
          </>
        }
      />

      {inputs && (
        <div className="grid gap-x-8 gap-y-5 rounded-xl border border-rule bg-card p-5 sm:grid-cols-2 lg:grid-cols-4">
          {QUICK.map((f) => {
            const v = Number(inputs[f.key] ?? 0);
            return (
              <div key={f.key}>
                <div className="flex items-baseline justify-between gap-2">
                  <Label id={`sl-${f.key}`} className="text-[13px] text-slate">
                    {f.label}
                  </Label>
                  <span className="num text-sm font-semibold">{f.fmt(v)}</span>
                </div>
                <Slider
                  aria-labelledby={`sl-${f.key}`}
                  className="mt-3"
                  min={f.min}
                  max={Math.max(f.max, v)}
                  step={f.step}
                  value={[v]}
                  onValueChange={(val) => set(f.key, Array.isArray(val) ? val[0] : val)}
                />
              </div>
            );
          })}
          <div className="flex items-end">
            <Button variant="link" className="px-0" onClick={() => setShowAll((s) => !s)}>
              {showAll ? "Hide other assumptions" : "Edit every assumption"}
            </Button>
          </div>
        </div>
      )}
      {showAll && inputs && (
        <div className="mt-5 rounded-xl border border-rule bg-card p-5">
          <AssumptionsForm values={inputs} onChange={set} errors={error ? errorsByField(error.fieldErrors) : {}} />
        </div>
      )}

      {error && (
        <Notice tone="error" className="mt-5" title="These inputs can't be calculated">
          {error.summary}
        </Notice>
      )}
      {result && (
        <div className={error ? "opacity-50" : undefined} aria-live="polite">
          <div className="mt-6">
            <HeadlineFigures r={result} />
          </div>
          <Warnings r={result} />
          <AnalysisBody r={result} />
        </div>
      )}
    </>
  );
}
