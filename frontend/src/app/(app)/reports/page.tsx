"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { toast } from "sonner";

import { EmptyState, ErrorState, LoadingRows, PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, ApiError, download } from "@/lib/api";
import { dateTime } from "@/lib/format";
import type { Report } from "@/lib/types";

export default function ReportsPage() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["reports"], queryFn: () => api<Report[]>("/reports") });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/reports/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reports"] }),
  });
  return (
    <>
      <PageHeader
        title="Reports"
        description="PDF reports and CSV exports you've generated. Each records the assumptions, formulas, data sources and the date it was produced."
      />
      {q.isLoading && <LoadingRows />}
      {q.error && <ErrorState error={q.error} retry={() => q.refetch()} />}
      {q.data?.length === 0 && (
        <EmptyState title="No reports yet">
          Open a saved analysis and choose <strong className="text-ink">Download PDF report</strong> or <strong className="text-ink">Export CSV</strong>, or export a comparison.
        </EmptyState>
      )}
      {q.data && q.data.length > 0 && (
        <div className="overflow-x-auto">
          <Table className="min-w-[620px]">
            <TableHeader>
              <TableRow>
                <TableHead>Report</TableHead>
                <TableHead>Format</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Size</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {q.data.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>
                    {r.analysis_id ? (
                      <Link href={`/analyses/${r.analysis_id}`} className="font-medium hover:underline">
                        {r.title}
                      </Link>
                    ) : (
                      <span className="font-medium">{r.title}</span>
                    )}
                  </TableCell>
                  <TableCell className="text-slate">{r.kind.toUpperCase()}</TableCell>
                  <TableCell className="text-slate">{dateTime(r.created_at)}</TableCell>
                  <TableCell className="num text-right text-slate">{(r.size_bytes / 1024).toFixed(1)} KB</TableCell>
                  <TableCell className="space-x-1 text-right">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => download(`/reports/${r.id}/download`, r.filename).catch((e) => toast.error(e instanceof ApiError ? e.summary : "Download failed"))}
                    >
                      Download
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => remove.mutate(r.id)}>
                      Delete
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  );
}
