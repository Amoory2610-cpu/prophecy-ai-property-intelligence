import type { Unit } from "./types";

const gbp0 = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 });
const gbp2 = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP", minimumFractionDigits: 2 });

export function money(value: number | null | undefined, opts: { pence?: boolean } = {}): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  const f = opts.pence ? gbp2 : gbp0;
  return f.format(value).replace("-", "−");
}

export function compactMoney(value: number | null | undefined): string {
  if (value === null || value === undefined) return "n/a";
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `£${(value / 1_000_000).toFixed(abs >= 10_000_000 ? 0 : 2)}m`;
  if (abs >= 10_000) return `£${Math.round(value / 1000)}k`;
  return money(value);
}

export function pct(value: number | null | undefined, places = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  return `${value.toFixed(places).replace("-", "−")}%`;
}

export function formatValue(value: number | null | undefined, unit: Unit): string {
  switch (unit) {
    case "gbp":
      return money(value);
    case "gbp_month":
      return value === null || value === undefined ? "n/a" : `${money(value)}/mo`;
    case "percent":
      return pct(value);
    case "multiple":
      return value === null || value === undefined ? "n/a" : `${value.toFixed(2)}×`;
    default:
      return value === null || value === undefined ? "n/a" : String(value);
  }
}

/** Format an engine input value for the "working" panel. */
export function formatInput(key: string, value: unknown): string {
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "number") {
    if (key.endsWith("_pct")) return `${value}%`;
    if (key.endsWith("_years")) return `${value} years`;
    return money(value);
  }
  if (Array.isArray(value)) return value.map((v) => (typeof v === "number" ? compactMoney(v) : String(v))).join(", ");
  if (value === null || value === undefined) return "none";
  return String(value).replace(/_/g, " ");
}

export function signClass(value: number | null | undefined): string {
  if (value === null || value === undefined) return "";
  return value < 0 ? "text-brick" : value > 0 ? "text-wood" : "";
}

export function date(value: string | null | undefined): string {
  if (!value) return "n/a";
  return new Date(value).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return "n/a";
  return new Date(value).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export const PROPERTY_TYPES: Record<string, string> = {
  detached: "Detached",
  semi_detached: "Semi-detached",
  terraced: "Terraced",
  flat: "Flat",
  bungalow: "Bungalow",
  other: "Other",
};

export const REGIONS: Record<string, string> = {
  england: "England",
  wales: "Wales",
  scotland: "Scotland",
  northern_ireland: "Northern Ireland",
};

export const RENT_SOURCES: Record<string, string> = {
  user_estimate: "Your estimate",
  agent_quote: "Letting agent quote",
  current_tenancy: "Current tenancy",
  demo: "Illustrative (demo)",
};
