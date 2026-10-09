"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { ErrorState, LoadingRows, Notice, PageHeader, Section } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, ApiError, download } from "@/lib/api";
import { date, dateTime } from "@/lib/format";
import { useMe } from "@/lib/session";
import type { DataImport } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS: Record<DataImport["status"], [string, string]> = {
  completed: ["Imported", "bg-wood-soft text-wood"],
  completed_with_errors: ["Imported with rejected rows", "bg-ochre-soft text-ochre"],
  failed: ["Failed", "bg-brick-soft text-brick"],
  processing: ["Processing", "bg-muted text-slate"],
};

function Uploader({ endpoint, label, onDone }: { endpoint: string; label: string; onDone: (r: DataImport) => void }) {
  const ref = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const upload = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append("file", file!);
      return api<DataImport>(endpoint, { method: "POST", form });
    },
    onSuccess: (r) => {
      setFile(null);
      if (ref.current) ref.current.value = "";
      onDone(r);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.summary : "Upload failed"),
  });
  return (
    <div className="flex flex-wrap items-center gap-3">
      <input
        ref={ref}
        type="file"
        accept=".csv,text/csv"
        aria-label={`CSV file for: ${label.toLowerCase()}`}
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        className="text-sm file:mr-3 file:rounded-md file:border file:border-input file:bg-card file:px-3 file:py-1.5 file:text-sm file:font-medium"
      />
      <Button onClick={() => upload.mutate()} disabled={!file || upload.isPending}>
        {upload.isPending ? "Importing…" : label}
      </Button>
    </div>
  );
}

export default function DataPage() {
  const qc = useQueryClient();
  const { data: me } = useMe();
  const q = useQuery({ queryKey: ["imports"], queryFn: () => api<DataImport[]>("/imports") });
  const [last, setLast] = useState<DataImport | null>(null);

  const done = (r: DataImport) => {
    setLast(r);
    qc.invalidateQueries();
    if (r.status === "failed") toast.error("Nothing was imported. See the errors below.");
    else toast.success(`${r.rows_imported.toLocaleString("en-GB")} rows imported`);
  };

  return (
    <>
      <PageHeader
        title="Data sources"
        description="Where the data in Prophecy comes from, when it arrived and what was rejected. Imported files are validated row by row, and nothing invalid is stored."
      />

      <div className="grid gap-10 lg:grid-cols-2">
        <Section title="Your property shortlist (CSV)" description="Private to your account. Required columns: title, asking_price, estimated_monthly_rent.">
          <Uploader endpoint="/imports/properties" label="Import properties" onDone={done} />
          <button
            type="button"
            className="mt-3 text-sm font-medium text-wood underline underline-offset-2"
            onClick={() => download("/imports/templates/properties.csv", "prophecy-properties-template.csv")}
          >
            Download the CSV template
          </button>
          <p className="mt-2 text-xs leading-relaxed text-slate">
            Optional columns: address_line, town, postcode, region, property_type, tenure, bedrooms, bathrooms, floor_area_sqm, rent_source, listing_url,
            notes. Rows are labelled as CSV imports, and the rent is recorded as your estimate unless you say otherwise.
          </p>
        </Section>

        <Section
          title="HM Land Registry Price Paid Data"
          description="Shared market data behind comparable sales and the market pages. Open Government Licence v3.0."
        >
          {me?.is_admin ? (
            <>
              <Uploader endpoint="/imports/land-registry" label="Import sales file" onDone={done} />
              <p className="mt-2 text-xs leading-relaxed text-slate">
                Accepts the official CSV files (yearly, monthly or complete). Uploads are limited to 50 MB; for full-year files use the command line:{" "}
                <code className="rounded bg-muted px-1">python -m app.cli import-ppd pp-2024.csv</code>
              </p>
            </>
          ) : (
            <p className="text-sm leading-relaxed text-slate">
              Only administrators can import market data because it&apos;s shared by every account. Ask your administrator, or run{" "}
              <code className="rounded bg-muted px-1">python -m app.cli make-admin you@example.com</code> on your own installation.
            </p>
          )}
          <a
            href="https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads"
            target="_blank"
            rel="noreferrer"
            className="mt-3 inline-block text-sm font-medium text-wood underline underline-offset-2"
          >
            Download files from GOV.UK
          </a>
        </Section>
      </div>

      {last && <ImportResult r={last} />}

      <Section title="Import history">
        {q.isLoading && <LoadingRows />}
        {q.error && <ErrorState error={q.error} />}
        {q.data?.length === 0 && <p className="text-sm text-slate">No imports yet.</p>}
        {q.data && q.data.length > 0 && (
          <div className="overflow-x-auto">
            <Table className="min-w-[760px]">
              <TableHeader>
                <TableRow>
                  <TableHead>File</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Imported</TableHead>
                  <TableHead className="text-right">Rejected</TableHead>
                  <TableHead>Data covers</TableHead>
                  <TableHead>When</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {q.data.map((r) => (
                  <TableRow key={r.id} className="cursor-pointer" onClick={() => setLast(r)}>
                    <TableCell className="font-medium">{r.filename}</TableCell>
                    <TableCell className="text-slate">{r.source_name}</TableCell>
                    <TableCell>
                      <span className={cn("rounded-sm px-1.5 py-px text-[11px] font-semibold", STATUS[r.status][1])}>{STATUS[r.status][0]}</span>
                    </TableCell>
                    <TableCell className="num text-right">{r.rows_imported.toLocaleString("en-GB")}</TableCell>
                    <TableCell className="num text-right">{r.rows_rejected.toLocaleString("en-GB")}</TableCell>
                    <TableCell className="text-slate">{r.data_from ? `${date(r.data_from)} to ${date(r.data_to)}` : "n/a"}</TableCell>
                    <TableCell className="text-slate">{dateTime(r.completed_at ?? r.created_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <p className="mt-2 text-xs text-slate">Select a row to see its errors and attribution.</p>
          </div>
        )}
      </Section>

      <Section title="What isn't connected">
        <ul className="list-disc space-y-1.5 pl-4 text-sm leading-relaxed text-slate">
          <li>No live listings feed. Portals such as Rightmove and Zoopla don&apos;t offer public APIs, and Prophecy doesn&apos;t scrape them.</li>
          <li>No rental market data. Rents are your own figures, labelled by source on every report.</li>
          <li>Scotland and Northern Ireland sales are not in the Land Registry dataset, so comparables cover England and Wales only.</li>
        </ul>
      </Section>
    </>
  );
}

function ImportResult({ r }: { r: DataImport }) {
  return (
    <Notice tone={r.status === "failed" ? "error" : r.rows_rejected ? "warn" : "info"} title={`${r.filename}: ${STATUS[r.status][0].toLowerCase()}`} className="mb-10">
      <p className="num">
        {r.rows_imported.toLocaleString("en-GB")} of {r.rows_total.toLocaleString("en-GB")} rows imported, {r.rows_rejected.toLocaleString("en-GB")} rejected.
        SHA-256 {r.sha256.slice(0, 12)}…
      </p>
      {r.errors.length > 0 && (
        <div className="mt-2 max-h-56 overflow-y-auto rounded-md border border-rule bg-card">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-card text-left text-slate">
              <tr>
                <th className="px-2 py-1 font-medium">Row</th>
                <th className="px-2 py-1 font-medium">Field</th>
                <th className="px-2 py-1 font-medium">Problem</th>
              </tr>
            </thead>
            <tbody>
              {r.errors.map((e, i) => (
                <tr key={i} className="border-t border-rule">
                  <td className="num px-2 py-1">{e.row || "file"}</td>
                  <td className="px-2 py-1">{e.field ?? e.transaction_id ?? ""}</td>
                  <td className="px-2 py-1">{e.error}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {r.attribution && <p className="mt-2 text-xs text-slate">{r.attribution}</p>}
    </Notice>
  );
}
