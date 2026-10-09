"use client";

import { useState } from "react";

import { errorsByField } from "@/components/assumptions-form";
import { Notice } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { PROPERTY_TYPES, REGIONS, RENT_SOURCES } from "@/lib/format";
import type { Property } from "@/lib/types";

export type PropertyDraft = {
  title: string;
  address_line: string;
  town: string;
  postcode: string;
  region: string;
  property_type: string;
  tenure: string;
  bedrooms: string;
  bathrooms: string;
  floor_area_sqm: string;
  asking_price: string;
  estimated_monthly_rent: string;
  rent_source: string;
  listing_url: string;
  notes: string;
  ground_rent_service_annual: string;
};

export function draftFrom(p?: Property): PropertyDraft {
  const s = (v: unknown) => (v === null || v === undefined ? "" : String(v));
  return {
    title: s(p?.title),
    address_line: s(p?.address_line),
    town: s(p?.town),
    postcode: s(p?.postcode),
    region: p?.region ?? "england",
    property_type: p?.property_type ?? "flat",
    tenure: p?.tenure ?? "leasehold",
    bedrooms: s(p?.bedrooms),
    bathrooms: s(p?.bathrooms),
    floor_area_sqm: s(p?.floor_area_sqm),
    asking_price: s(p?.asking_price),
    estimated_monthly_rent: s(p?.estimated_monthly_rent),
    rent_source: p?.rent_source === "demo" ? "demo" : p?.rent_source ?? "user_estimate",
    listing_url: s(p?.listing_url),
    notes: s(p?.notes),
    ground_rent_service_annual: s(p?.assumption_overrides?.ground_rent_service_annual),
  };
}

export function payloadFrom(d: PropertyDraft, existingOverrides: Record<string, unknown> = {}) {
  const num = (v: string) => (v.trim() === "" ? null : Number(v.replace(/[£,\s]/g, "")));
  const overrides = { ...existingOverrides };
  if (d.ground_rent_service_annual.trim() === "") delete overrides.ground_rent_service_annual;
  else overrides.ground_rent_service_annual = num(d.ground_rent_service_annual);
  return {
    title: d.title.trim(),
    address_line: d.address_line.trim(),
    town: d.town.trim(),
    postcode: d.postcode.trim() || null,
    region: d.region,
    property_type: d.property_type,
    tenure: d.tenure,
    bedrooms: num(d.bedrooms),
    bathrooms: num(d.bathrooms),
    floor_area_sqm: num(d.floor_area_sqm),
    asking_price: num(d.asking_price),
    estimated_monthly_rent: num(d.estimated_monthly_rent),
    rent_source: d.rent_source,
    listing_url: d.listing_url.trim() || null,
    notes: d.notes,
    assumption_overrides: overrides,
  };
}

function Field({
  id,
  label,
  error,
  hint,
  children,
  wide,
}: {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <div className={wide ? "sm:col-span-2" : undefined}>
      <Label htmlFor={id} className="text-[13px] text-slate">
        {label}
      </Label>
      <div className="mt-1">{children}</div>
      {error ? <p className="mt-1 text-xs text-brick">{error}</p> : hint && <p className="mt-1 text-xs text-slate">{hint}</p>}
    </div>
  );
}

const selectCls =
  "h-9 w-full rounded-md border border-input bg-card px-2.5 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-ring/40";

export function PropertyForm({
  initial,
  submitLabel,
  onSubmit,
  isDemo,
}: {
  initial: PropertyDraft;
  submitLabel: string;
  onSubmit: (d: PropertyDraft) => Promise<void>;
  isDemo?: boolean;
}) {
  const [d, setD] = useState(initial);
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const errs = error ? errorsByField(error.fieldErrors) : {};
  const set = (k: keyof PropertyDraft) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setD((x) => ({ ...x, [k]: e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit(d);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, "Could not save the property."));
    } finally {
      setBusy(false);
    }
  }

  const input = (k: keyof PropertyDraft, props: React.ComponentProps<typeof Input> = {}) => (
    <Input id={`p-${k}`} value={d[k]} onChange={set(k)} aria-invalid={Boolean(errs[k])} className="bg-card" {...props} />
  );

  return (
    <form onSubmit={submit} className="max-w-3xl space-y-8" noValidate>
      {error && (
        <Notice tone="error" title="Check the highlighted fields">
          {error.summary}
        </Notice>
      )}
      <fieldset className="grid gap-4 sm:grid-cols-2">
        <legend className="mb-3 text-sm font-semibold text-slate">The property</legend>
        <Field id="p-title" label="Name" error={errs.title} hint="Something you'll recognise, such as the street and size." wide>
          {input("title", { required: true, placeholder: "Two-bed flat, Hyde Park Road" })}
        </Field>
        <Field id="p-address_line" label="Address" error={errs.address_line}>
          {input("address_line")}
        </Field>
        <Field id="p-town" label="Town or city" error={errs.town}>
          {input("town")}
        </Field>
        <Field id="p-postcode" label="Postcode" error={errs.postcode} hint="Used to find comparable Land Registry sales.">
          {input("postcode", { autoCapitalize: "characters" })}
        </Field>
        <Field id="p-region" label="Nation" error={errs.region} hint="Decides which property transaction tax applies.">
          <select id="p-region" value={d.region} onChange={set("region")} className={selectCls}>
            {Object.entries(REGIONS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </Field>
        <Field id="p-property_type" label="Type" error={errs.property_type}>
          <select id="p-property_type" value={d.property_type} onChange={set("property_type")} className={selectCls}>
            {Object.entries(PROPERTY_TYPES).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </Field>
        <Field id="p-tenure" label="Tenure" error={errs.tenure}>
          <select id="p-tenure" value={d.tenure} onChange={set("tenure")} className={selectCls}>
            <option value="freehold">Freehold</option>
            <option value="leasehold">Leasehold</option>
            <option value="share_of_freehold">Share of freehold</option>
          </select>
        </Field>
        <Field id="p-bedrooms" label="Bedrooms" error={errs.bedrooms}>
          {input("bedrooms", { type: "number", min: 0, inputMode: "numeric" })}
        </Field>
        <Field id="p-bathrooms" label="Bathrooms" error={errs.bathrooms}>
          {input("bathrooms", { type: "number", min: 0, inputMode: "numeric" })}
        </Field>
        <Field id="p-floor_area_sqm" label="Floor area (m²)" error={errs.floor_area_sqm}>
          {input("floor_area_sqm", { type: "number", min: 0, inputMode: "decimal" })}
        </Field>
        <Field id="p-listing_url" label="Listing link" error={errs.listing_url}>
          {input("listing_url", { type: "url", placeholder: "https://" })}
        </Field>
      </fieldset>

      <fieldset className="grid gap-4 sm:grid-cols-2">
        <legend className="mb-3 text-sm font-semibold text-slate">Price and rent</legend>
        {isDemo && (
          <Notice tone="warn" className="sm:col-span-2">
            This is a demo record: its price and rent are illustrative, not a real listing.
          </Notice>
        )}
        <Field id="p-asking_price" label="Asking price (£)" error={errs.asking_price}>
          {input("asking_price", { type: "number", min: 1, inputMode: "numeric", required: true })}
        </Field>
        <Field id="p-estimated_monthly_rent" label="Expected rent per month (£)" error={errs.estimated_monthly_rent}>
          {input("estimated_monthly_rent", { type: "number", min: 0, inputMode: "numeric", required: true })}
        </Field>
        <Field id="p-rent_source" label="Where the rent figure comes from" error={errs.rent_source} hint="Shown on reports so readers know how firm it is.">
          <select id="p-rent_source" value={d.rent_source} onChange={set("rent_source")} className={selectCls}>
            {Object.entries(RENT_SOURCES)
              .filter(([v]) => v !== "demo" || d.rent_source === "demo")
              .map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
          </select>
        </Field>
        <Field id="p-ground_rent_service_annual" label="Ground rent and service charge (£/yr)" error={errs.ground_rent_service_annual} hint="Leave blank to use your default.">
          {input("ground_rent_service_annual", { type: "number", min: 0, inputMode: "numeric" })}
        </Field>
        <Field id="p-notes" label="Notes" error={errs.notes} wide>
          <Textarea id="p-notes" value={d.notes} onChange={set("notes")} rows={3} className="bg-card" />
        </Field>
      </fieldset>

      <Button type="submit" disabled={busy} className="h-10 px-5">
        {busy ? "Saving…" : submitLabel}
      </Button>
    </form>
  );
}
