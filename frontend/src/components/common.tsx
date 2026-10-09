"use client";

import { AlertTriangle, Info } from "lucide-react";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-4 border-b border-rule pb-5">
      <div className="max-w-2xl">
        <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-[2.1rem]">{title}</h1>
        {description && <div className="mt-1.5 text-[15px] leading-relaxed text-slate">{description}</div>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

/** A titled section separated by a rule rather than boxed in a card. */
export function Section({
  title,
  description,
  aside,
  children,
  className,
}: {
  title: string;
  description?: React.ReactNode;
  aside?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("mb-10", className)}>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-ink">{title}</h2>
          {description && <p className="mt-0.5 max-w-2xl text-sm text-slate">{description}</p>}
        </div>
        {aside}
      </div>
      {children}
    </section>
  );
}

export function Panel({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("rounded-xl border border-rule bg-card p-5", className)}>{children}</div>;
}

export function DemoBadge() {
  return (
    <span
      className="inline-flex items-center rounded-sm border border-ochre/40 bg-ochre-soft px-1.5 py-px text-[11px] font-semibold text-ochre"
      title="Demonstration record: price and rent are illustrative, not a real listing"
    >
      Demo data
    </span>
  );
}

export function SourceBadge({ source }: { source: string }) {
  const label = { manual: "Entered manually", csv_import: "CSV import", demo: "Demo" }[source] ?? source;
  if (source === "demo") return <DemoBadge />;
  return <span className="rounded-sm bg-muted px-1.5 py-px text-[11px] font-medium text-slate">{label}</span>;
}

export function Notice({
  tone = "info",
  title,
  children,
  className,
}: {
  tone?: "info" | "warn" | "error";
  title?: string;
  children: React.ReactNode;
  className?: string;
}) {
  const styles = {
    info: "border-rule bg-card text-ink",
    warn: "border-ochre/30 bg-ochre-soft text-ink",
    error: "border-brick/30 bg-brick-soft text-ink",
  }[tone];
  const Icon = tone === "info" ? Info : AlertTriangle;
  const iconColour = { info: "text-slate", warn: "text-ochre", error: "text-brick" }[tone];
  return (
    <div role={tone === "error" ? "alert" : undefined} className={cn("flex gap-3 rounded-lg border p-3.5 text-sm", styles, className)}>
      <Icon className={cn("mt-0.5 size-4 shrink-0", iconColour)} aria-hidden />
      <div className="space-y-1 leading-relaxed">
        {title && <p className="font-semibold">{title}</p>}
        <div>{children}</div>
      </div>
    </div>
  );
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const message = error instanceof ApiError ? error.summary : "Something went wrong loading this page.";
  return (
    <Notice tone="error" title="This could not be loaded">
      <p>{message}</p>
      {retry && (
        <button type="button" onClick={retry} className="mt-2 font-medium text-wood underline underline-offset-2">
          Try again
        </button>
      )}
    </Notice>
  );
}

export function LoadingRows({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-9 w-full" />
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children?: React.ReactNode;
  action?: { href: string; label: string } | React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-dashed border-input bg-card/60 px-6 py-10 text-center">
      <p className="font-heading text-lg font-semibold text-ink">{title}</p>
      {children && <div className="mx-auto mt-1.5 max-w-md text-sm text-slate">{children}</div>}
      {action && (
        <div className="mt-4 flex justify-center">
          {typeof action === "object" && action !== null && "href" in action ? (
            <Link href={action.href} className={buttonVariants()}>
              {action.label}
            </Link>
          ) : (
            action
          )}
        </div>
      )}
    </div>
  );
}

/** A figure with a small caption; used sparingly for the handful of headline numbers. */
export function Figure({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  tone?: "pos" | "neg";
}) {
  return (
    <div className="min-w-0">
      <p className="text-[13px] text-slate">{label}</p>
      <p
        className={cn(
          "num font-heading mt-0.5 text-2xl font-semibold tracking-tight text-ink",
          tone === "pos" && "text-wood",
          tone === "neg" && "text-brick",
        )}
      >
        {value}
      </p>
      {sub && <p className="mt-0.5 text-xs text-slate">{sub}</p>}
    </div>
  );
}
