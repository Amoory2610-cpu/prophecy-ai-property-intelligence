"use client";

import { ChevronDown } from "lucide-react";
import { useId, useState } from "react";

import { cn } from "@/lib/utils";
import { formatInput, formatValue, signClass } from "@/lib/format";
import type { Metric } from "@/lib/types";

/** Small label distinguishing estimates (rule- or assumption-dependent) from calculations. */
export function BasisTag({ basis }: { basis: Metric["basis"] }) {
  if (basis !== "estimate") return null;
  return (
    <span className="rounded-sm bg-ochre-soft px-1.5 py-px text-[11px] font-medium text-ochre" title="Depends on tax rules or growth assumptions">
      estimate
    </span>
  );
}

const SIGNED = new Set([
  "monthly_cash_flow",
  "annual_cash_flow",
  "monthly_cash_flow_after_tax",
  "noi_annual",
  "cash_on_cash",
  "irr",
  "total_profit",
]);

/**
 * One ledger line. The figure can be expanded to "show the working": the formula,
 * the actual inputs used and any note, so no number on the page is a black box.
 */
export function LedgerRow({ metric, emphasis = false }: { metric: Metric; emphasis?: boolean }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <div className="border-b border-rule last:border-b-0">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
        className="group flex w-full items-baseline gap-2 py-2.5 text-left outline-none focus-visible:bg-muted/60"
      >
        <span className={cn("text-sm", emphasis ? "font-semibold text-ink" : "text-ink/90")}>{metric.label}</span>
        <BasisTag basis={metric.basis} />
        <span className="leader" aria-hidden />
        <span
          className={cn(
            "num text-right",
            emphasis ? "text-lg font-semibold" : "text-sm font-medium",
            SIGNED.has(metric.key) && signClass(metric.value),
          )}
        >
          {formatValue(metric.value, metric.unit)}
        </span>
        <ChevronDown
          aria-hidden
          className={cn("size-3.5 shrink-0 self-center text-slate transition-transform", open && "rotate-180")}
        />
        <span className="sr-only">{open ? "Hide working" : "Show working"}</span>
      </button>
      {open && (
        <div id={id} className="working mb-3 rounded-r-md px-3 py-2.5 text-[13px] leading-relaxed">
          <p className="font-medium text-ink">{metric.formula}</p>
          <dl className="mt-1.5 grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5 text-slate">
            {Object.entries(metric.inputs).map(([k, v]) => (
              <div key={k} className="contents">
                <dt>{k.replace(/_/g, " ")}</dt>
                <dd className="num text-ink">{formatInput(k, v)}</dd>
              </div>
            ))}
          </dl>
          {metric.note && <p className="mt-1.5 text-slate">{metric.note}</p>}
        </div>
      )}
    </div>
  );
}

export function Ledger({
  metrics,
  keys,
  emphasis = [],
  className,
}: {
  metrics: Metric[];
  keys: string[];
  emphasis?: string[];
  className?: string;
}) {
  const byKey = new Map(metrics.map((m) => [m.key, m]));
  return (
    <div className={className}>
      {keys
        .map((k) => byKey.get(k))
        .filter((m): m is Metric => Boolean(m))
        .map((m) => (
          <LedgerRow key={m.key} metric={m} emphasis={emphasis.includes(m.key)} />
        ))}
    </div>
  );
}
