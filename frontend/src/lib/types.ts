// Mirrors backend/app/schemas and backend/app/finance/engine.py.

export type Unit = "gbp" | "gbp_month" | "percent" | "ratio" | "multiple";
export type Basis = "calculated" | "estimate";
export type Region = "england" | "northern_ireland" | "scotland" | "wales";

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_admin: boolean;
  created_at: string;
}

export interface Property {
  id: string;
  title: string;
  address_line: string;
  town: string;
  postcode: string | null;
  region: Region;
  property_type: string;
  tenure: string;
  bedrooms: number | null;
  bathrooms: number | null;
  floor_area_sqm: number | null;
  asking_price: number;
  estimated_monthly_rent: number;
  rent_source: string;
  listing_url: string | null;
  notes: string;
  data_source: "manual" | "csv_import" | "demo";
  import_id: string | null;
  is_demo: boolean;
  assumption_overrides: Record<string, unknown>;
  gross_yield_pct: number | null;
  created_at: string;
  updated_at: string;
}

export interface PropertyPage {
  items: Property[];
  total: number;
  page: number;
  page_size: number;
}

export interface Metric {
  key: string;
  label: string;
  value: number | null;
  unit: Unit;
  formula: string;
  inputs: Record<string, unknown>;
  basis: Basis;
  note: string | null;
}

export interface TaxBand {
  lower: number;
  upper: number | null;
  rate_pct: number;
  taxable_amount: number;
  tax: number;
}

export interface ProjectionYear {
  year: number;
  gross_rent: number;
  collected_rent: number;
  operating_expenses: number;
  net_operating_income: number;
  debt_service: number;
  interest: number;
  principal_repaid: number;
  pre_tax_cash_flow: number;
  tax: number;
  after_tax_cash_flow: number;
  property_value: number;
  loan_balance: number;
  equity: number;
}

export interface BreakEven {
  key: string;
  label: string;
  value: number | null;
  unit: Unit;
  current: number;
  explanation: string;
}

export interface SensitivityPoint {
  label: string;
  monthly_cash_flow: number;
  irr_pct: number | null;
  net_yield_pct: number | null;
}

export interface SensitivityRow {
  driver: string;
  description: string;
  low: SensitivityPoint;
  high: SensitivityPoint;
  cash_flow_swing: number;
}

export interface ScenarioAdjustments {
  rent_change_pct: number;
  interest_rate_change_pp: number;
  vacancy_change_pp: number;
  capital_growth_change_pp: number;
  expense_change_pct: number;
  purchase_price_change_pct: number;
}

export interface ScenarioResult {
  name: string;
  adjustments: ScenarioAdjustments;
  monthly_cash_flow: number;
  annual_cash_flow: number;
  net_yield_pct: number | null;
  cash_on_cash_pct: number | null;
  irr_pct: number | null;
  total_profit: number;
  initial_cash_required: number;
  drivers: { assumption: string; change: number; monthly_cash_flow_impact: number; irr_impact_pp: number | null }[];
}

export interface DealResults {
  engine_version: string;
  inputs: DealInputs;
  metrics: Metric[];
  transaction_tax: {
    name: string;
    total: number;
    effective_rate_pct: number;
    overridden: boolean;
    bands: TaxBand[];
    surcharge_total: number;
    assumptions: string[];
    source_url: string;
    rules_reviewed_on: string;
  };
  tax_formula: string;
  projection: ProjectionYear[];
  sale: {
    year: number;
    sale_price: number;
    selling_costs: number;
    loan_repayment: number;
    base_cost: number;
    gain: number;
    capital_gains_tax: number;
    cgt_formula: string;
    net_sale_proceeds: number;
  };
  returns: {
    total_cash_invested: number;
    total_cash_flow: number;
    net_sale_proceeds: number;
    total_profit: number;
    equity_multiple: number | null;
    irr_pct: number | null;
    cash_flows: number[];
  };
  assumptions: string[];
  warnings: string[];
  tax_notes: string[];
  tax_rules_reviewed_on: string;
  break_even: BreakEven[];
  sensitivity: { base: SensitivityPoint; rows: SensitivityRow[] };
  scenarios: ScenarioResult[];
}

export interface DealInputs {
  purchase_price: number;
  region: Region;
  buyer_type: "additional_property" | "first_time_buyer" | "home_mover";
  non_resident: boolean;
  transaction_tax_override: number | null;
  legal_fees: number;
  survey_fees: number;
  refurbishment_costs: number;
  other_purchase_costs: number;
  financing: "mortgage" | "cash";
  deposit_pct: number;
  mortgage_type: "repayment" | "interest_only";
  interest_rate_pct: number;
  term_years: number;
  mortgage_fee: number;
  add_fee_to_loan: boolean;
  stress_rate_pct: number;
  required_icr_pct: number;
  monthly_rent: number;
  vacancy_pct: number;
  management_pct: number;
  maintenance_pct: number;
  insurance_annual: number;
  ground_rent_service_annual: number;
  other_costs_annual: number;
  holding_years: number;
  capital_growth_pct: number;
  rent_growth_pct: number;
  cost_inflation_pct: number;
  selling_costs_pct: number;
  ownership: "individual" | "company" | "none";
  tax_band: "basic" | "higher" | "additional";
  income_tax_rate_override_pct: number | null;
  include_cgt: boolean;
}

export type Headline = {
  gross_yield: number | null;
  net_yield: number | null;
  monthly_cash_flow: number | null;
  cash_on_cash: number | null;
  irr: number | null;
  initial_cash_required: number | null;
};

export interface AnalysisSummary {
  id: string;
  property_id: string | null;
  name: string;
  engine_version: string;
  created_at: string;
  headline: Headline;
}

export interface Analysis extends AnalysisSummary {
  inputs: DealInputs;
  results: DealResults;
}

export interface Explanation {
  id: string;
  analysis_id: string;
  provider: string;
  model: string;
  created_at: string;
  content: {
    summary: string;
    strengths: string[];
    weaknesses: string[];
    risks: { title: string; detail: string; severity: "low" | "medium" | "high" }[];
    yield_and_cash_flow: string;
    sensitivity: string;
    improvements: string[];
    caveats: string[];
    unverified_figures: string[];
    notice: string | null;
  };
}

export interface DataImport {
  id: string;
  kind: "properties_csv" | "land_registry_ppd";
  status: "processing" | "completed" | "completed_with_errors" | "failed";
  filename: string;
  sha256: string;
  rows_total: number;
  rows_imported: number;
  rows_rejected: number;
  errors: { row: number; field?: string; error: string; transaction_id?: string }[];
  source_name: string;
  source_url: string | null;
  licence: string | null;
  attribution: string | null;
  data_from: string | null;
  data_to: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface Coverage {
  transactions: number;
  earliest_transaction: string | null;
  latest_transaction: string | null;
  last_imported_at: string | null;
  source_name: string;
  source_url: string;
  licence: string;
  attribution: string;
  days_since_latest_transaction: number | null;
}

export interface PriceStats {
  count: number;
  median?: number;
  mean?: number;
  p10?: number;
  p25?: number;
  p75?: number;
  p90?: number;
  low_sample?: boolean;
}

export interface Comparables {
  available: boolean;
  message?: string;
  level?: "sector" | "district";
  area?: string;
  property_type?: string | null;
  period?: { from: string; to: string };
  stats?: PriceStats;
  sales?: {
    date: string;
    price: number;
    address: string;
    postcode: string;
    property_type: string;
    new_build: boolean;
    tenure: string;
  }[];
}

export interface Valuation {
  estimate: number;
  range_low: number;
  range_high: number;
  sample_size: number;
  confidence: "higher" | "moderate" | "low";
  asking_vs_median_pct: number;
  method: string;
  limitations: string[];
}

export interface Report {
  id: string;
  analysis_id: string | null;
  comparison_id: string | null;
  kind: "pdf" | "csv";
  title: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

export interface Watchlist {
  id: string;
  name: string;
  description: string;
  created_at: string;
  items: { id: string; property_id: string; note: string; added_at: string; property: Property }[];
}

export interface Comparison {
  id: string;
  name: string;
  assumptions: Record<string, unknown>;
  property_ids: string[];
  created_at: string;
  updated_at: string;
}
