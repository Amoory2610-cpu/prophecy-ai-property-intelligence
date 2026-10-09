"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type { DealInputs } from "@/lib/types";
import { cn } from "@/lib/utils";

type NumberField = { key: keyof DealInputs; label: string; kind: "number"; suffix?: string; prefix?: string; min?: number; max?: number; step?: number; help?: string };
type SelectField = { key: keyof DealInputs; label: string; kind: "select"; options: [string, string][]; help?: string };
type BoolField = { key: keyof DealInputs; label: string; kind: "bool"; help?: string };
export type FieldDef = NumberField | SelectField | BoolField;

export const FIELD_GROUPS: { title: string; fields: FieldDef[] }[] = [
  {
    title: "Purchase",
    fields: [
      { key: "purchase_price", label: "Purchase price", kind: "number", prefix: "£", min: 1, step: 1000 },
      { key: "region", label: "Region", kind: "select", options: [["england", "England"], ["wales", "Wales"], ["scotland", "Scotland"], ["northern_ireland", "Northern Ireland"]] },
      {
        key: "buyer_type",
        label: "Buyer",
        kind: "select",
        options: [["additional_property", "Already own a home (higher rates)"], ["home_mover", "Replacing main home"], ["first_time_buyer", "First-time buyer"]],
        help: "Most buy-to-let purchases pay the higher rates for additional dwellings.",
      },
      { key: "non_resident", label: "Non-UK resident buyer", kind: "bool" },
      { key: "legal_fees", label: "Legal fees", kind: "number", prefix: "£", min: 0, step: 100 },
      { key: "survey_fees", label: "Survey", kind: "number", prefix: "£", min: 0, step: 50 },
      { key: "refurbishment_costs", label: "Refurbishment", kind: "number", prefix: "£", min: 0, step: 500 },
      { key: "other_purchase_costs", label: "Other purchase costs", kind: "number", prefix: "£", min: 0, step: 100 },
    ],
  },
  {
    title: "Mortgage",
    fields: [
      { key: "financing", label: "Financing", kind: "select", options: [["mortgage", "Mortgage"], ["cash", "Cash purchase"]] },
      { key: "deposit_pct", label: "Deposit", kind: "number", suffix: "%", min: 0, max: 100, step: 1 },
      { key: "mortgage_type", label: "Mortgage type", kind: "select", options: [["interest_only", "Interest only"], ["repayment", "Repayment"]] },
      { key: "interest_rate_pct", label: "Interest rate", kind: "number", suffix: "%", min: 0, max: 25, step: 0.05 },
      { key: "term_years", label: "Term", kind: "number", suffix: "years", min: 1, max: 40, step: 1 },
      { key: "mortgage_fee", label: "Arrangement fee", kind: "number", prefix: "£", min: 0, step: 100 },
      { key: "add_fee_to_loan", label: "Add fee to the loan", kind: "bool" },
      { key: "stress_rate_pct", label: "Lender stress rate", kind: "number", suffix: "%", min: 0, max: 25, step: 0.1 },
      { key: "required_icr_pct", label: "Required interest cover", kind: "number", suffix: "%", min: 100, max: 300, step: 5 },
    ],
  },
  {
    title: "Rent and running costs",
    fields: [
      { key: "monthly_rent", label: "Monthly rent", kind: "number", prefix: "£", min: 0, step: 25 },
      { key: "vacancy_pct", label: "Voids", kind: "number", suffix: "% of year", min: 0, max: 100, step: 0.5 },
      { key: "management_pct", label: "Management", kind: "number", suffix: "% of rent", min: 0, max: 50, step: 0.5 },
      { key: "maintenance_pct", label: "Maintenance", kind: "number", suffix: "% of rent", min: 0, max: 50, step: 0.5 },
      { key: "insurance_annual", label: "Insurance", kind: "number", prefix: "£", suffix: "/yr", min: 0, step: 25 },
      { key: "ground_rent_service_annual", label: "Ground rent and service charge", kind: "number", prefix: "£", suffix: "/yr", min: 0, step: 50 },
      { key: "other_costs_annual", label: "Other costs", kind: "number", prefix: "£", suffix: "/yr", min: 0, step: 50, help: "Safety certificates, licensing, accountancy." },
    ],
  },
  {
    title: "Growth and exit",
    fields: [
      { key: "holding_years", label: "Holding period", kind: "number", suffix: "years", min: 1, max: 40, step: 1 },
      { key: "capital_growth_pct", label: "Capital growth", kind: "number", suffix: "%/yr", min: -20, max: 20, step: 0.25 },
      { key: "rent_growth_pct", label: "Rent growth", kind: "number", suffix: "%/yr", min: -20, max: 20, step: 0.25 },
      { key: "cost_inflation_pct", label: "Cost inflation", kind: "number", suffix: "%/yr", min: -20, max: 20, step: 0.25 },
      { key: "selling_costs_pct", label: "Selling costs", kind: "number", suffix: "% of sale", min: 0, max: 15, step: 0.25 },
    ],
  },
  {
    title: "Tax scenario",
    fields: [
      { key: "ownership", label: "Owned by", kind: "select", options: [["individual", "Individual"], ["company", "Limited company"], ["none", "Ignore tax"]] },
      { key: "tax_band", label: "Income tax band", kind: "select", options: [["basic", "Basic rate"], ["higher", "Higher rate"], ["additional", "Additional rate"]] },
      {
        key: "income_tax_rate_override_pct",
        label: "Override income tax rate",
        kind: "number",
        suffix: "%",
        min: 0,
        max: 100,
        step: 1,
        help: "Leave blank to use the band rate, e.g. 22 for the announced 2027 property basic rate.",
      },
      { key: "include_cgt", label: "Include capital gains tax on sale", kind: "bool" },
    ],
  },
];

export function AssumptionsForm({
  values,
  onChange,
  exclude = [],
  errors = {},
  compact = false,
}: {
  values: Partial<DealInputs>;
  onChange: (key: keyof DealInputs, value: unknown) => void;
  exclude?: (keyof DealInputs)[];
  errors?: Record<string, string>;
  compact?: boolean;
}) {
  return (
    <div className={cn("grid gap-8", !compact && "lg:grid-cols-2")}>
      {FIELD_GROUPS.map((group) => {
        const fields = group.fields.filter((f) => !exclude.includes(f.key));
        if (!fields.length) return null;
        return (
          <fieldset key={group.title} className="min-w-0">
            <legend className="mb-3 text-sm font-semibold text-slate">{group.title}</legend>
            <div className="grid grid-cols-1 gap-x-4 gap-y-3 sm:grid-cols-2">
              {fields.map((f) => (
                <FieldControl key={f.key} field={f} value={values[f.key]} error={errors[f.key]} onChange={(v) => onChange(f.key, v)} />
              ))}
            </div>
          </fieldset>
        );
      })}
    </div>
  );
}

function FieldControl({ field, value, error, onChange }: { field: FieldDef; value: unknown; error?: string; onChange: (v: unknown) => void }) {
  const id = `f-${field.key}`;
  if (field.kind === "bool") {
    return (
      <div className="flex items-center justify-between gap-3 rounded-md border border-rule bg-card px-3 py-2 sm:col-span-2">
        <Label htmlFor={id} className="text-sm font-normal">
          {field.label}
        </Label>
        <Switch id={id} checked={Boolean(value)} onCheckedChange={(c) => onChange(c)} />
      </div>
    );
  }
  if (field.kind === "select") {
    return (
      <div className={cn(field.options.some(([, l]) => l.length > 24) && "sm:col-span-2")}>
        <Label htmlFor={id} className="text-[13px] text-slate">
          {field.label}
        </Label>
        <select
          id={id}
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
          className="mt-1 h-9 w-full rounded-md border border-input bg-card px-2.5 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
        >
          {field.options.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
        {field.help && <p className="mt-1 text-xs text-slate">{field.help}</p>}
      </div>
    );
  }
  return (
    <div>
      <Label htmlFor={id} className="text-[13px] text-slate">
        {field.label}
      </Label>
      <div className={cn("mt-1 flex h-9 items-center rounded-md border bg-card focus-within:ring-2 focus-within:ring-ring/40", error ? "border-brick" : "border-input")}>
        {field.prefix && <span className="pl-2.5 text-sm text-slate">{field.prefix}</span>}
        <Input
          id={id}
          type="number"
          inputMode="decimal"
          min={field.min}
          max={field.max}
          step={field.step}
          value={value === null || value === undefined ? "" : String(value)}
          onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
          aria-invalid={Boolean(error)}
          className="num h-full border-0 bg-transparent px-2 shadow-none focus-visible:ring-0"
        />
        {field.suffix && <span className="whitespace-nowrap pr-2.5 text-xs text-slate">{field.suffix}</span>}
      </div>
      {error ? <p className="mt-1 text-xs text-brick">{error}</p> : field.help && <p className="mt-1 text-xs text-slate">{field.help}</p>}
    </div>
  );
}

/** Map API field errors (e.g. "inputs.vacancy_pct") to field keys. */
export function errorsByField(fieldErrors: { field: string; message: string }[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const e of fieldErrors) {
    const key = e.field.split(".").pop() ?? e.field;
    out[key] = e.message;
  }
  return out;
}
