"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { AssumptionsForm, errorsByField } from "@/components/assumptions-form";
import { LoadingRows, Notice, PageHeader, Section } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { useMe } from "@/lib/session";
import type { DealInputs, User } from "@/lib/types";

export default function SettingsPage() {
  const qc = useQueryClient();
  const router = useRouter();
  const { data: me } = useMe();
  const assumptions = useQuery({
    queryKey: ["assumptions"],
    queryFn: () => api<{ values: Partial<DealInputs>; effective: Partial<DealInputs>; updated_at: string | null }>("/assumptions"),
  });
  const [edited, setEdited] = useState<Partial<DealInputs> | null>(null);
  const values = edited ?? assumptions.data?.effective ?? null;
  const setValues = (f: (x: Partial<DealInputs> | null) => Partial<DealInputs>) => setEdited(f(values));
  const [assumptionErr, setAssumptionErr] = useState<ApiError | null>(null);

  const saveAssumptions = useMutation({
    mutationFn: () => {
      const rest = Object.fromEntries(
        Object.entries(values ?? {}).filter(([k]) => !["purchase_price", "monthly_rent", "region"].includes(k)),
      );
      return api("/assumptions", { method: "PUT", body: { values: rest } });
    },
    onSuccess: () => {
      setAssumptionErr(null);
      qc.invalidateQueries({ queryKey: ["assumptions"] });
      toast.success("Default assumptions saved. New analyses will use them.");
    },
    onError: (e) => setAssumptionErr(e instanceof ApiError ? e : null),
  });

  const [name, setName] = useState<string | null>(null);
  const profile = useMutation({
    mutationFn: () => api<User>("/auth/me", { method: "PATCH", body: { full_name: name ?? me?.full_name ?? "" } }),
    onSuccess: (u) => {
      qc.setQueryData(["me"], u);
      toast.success("Profile updated");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.summary : "Could not update"),
  });

  const [pw, setPw] = useState({ current: "", next: "" });
  const password = useMutation({
    mutationFn: () => api("/auth/me/password", { method: "POST", body: { current_password: pw.current, new_password: pw.next } }),
    onSuccess: () => {
      setPw({ current: "", next: "" });
      toast.success("Password changed. Other devices have been signed out.");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.summary : "Could not change the password"),
  });

  const everywhere = useMutation({
    mutationFn: () => api("/auth/me/sign-out-everywhere", { method: "POST" }),
    onSuccess: () => {
      qc.clear();
      router.replace("/login");
    },
  });

  const [deletePw, setDeletePw] = useState("");
  const del = useMutation({
    mutationFn: () => api("/auth/me", { method: "DELETE", body: { password: deletePw } }),
    onSuccess: () => {
      qc.clear();
      router.replace("/");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.summary : "Could not delete the account"),
  });

  return (
    <>
      <PageHeader title="Account settings" description={me ? `Signed in as ${me.email}${me.is_admin ? " (administrator)" : ""}.` : undefined} />

      <Section
        title="Default assumptions"
        description={`Used for every new analysis unless a property or a single run overrides them.${assumptions.data?.updated_at ? ` Last saved ${dateTime(assumptions.data.updated_at)}.` : ""}`}
        aside={
          <Button onClick={() => saveAssumptions.mutate()} disabled={!values || saveAssumptions.isPending}>
            Save defaults
          </Button>
        }
      >
        {assumptionErr && (
          <Notice tone="error" className="mb-4">
            {assumptionErr.summary}
          </Notice>
        )}
        {values ? (
          <div className="rounded-xl border border-rule bg-card p-5">
            <AssumptionsForm
              values={values}
              onChange={(k, v) => setValues((x) => ({ ...x, [k]: v }))}
              exclude={["purchase_price", "monthly_rent", "region"]}
              errors={assumptionErr ? errorsByField(assumptionErr.fieldErrors) : {}}
            />
          </div>
        ) : (
          <LoadingRows />
        )}
      </Section>

      <div className="grid gap-10 lg:grid-cols-2">
        <Section title="Profile">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              profile.mutate();
            }}
            className="space-y-3"
          >
            <div>
              <Label htmlFor="s-name">Name</Label>
              <Input id="s-name" value={name ?? me?.full_name ?? ""} onChange={(e) => setName(e.target.value)} className="mt-1 bg-card" />
            </div>
            <Button type="submit" variant="outline" disabled={profile.isPending}>
              Save name
            </Button>
          </form>
        </Section>

        <Section title="Password">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              password.mutate();
            }}
            className="space-y-3"
          >
            <div>
              <Label htmlFor="s-cur">Current password</Label>
              <Input id="s-cur" type="password" autoComplete="current-password" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} className="mt-1 bg-card" />
            </div>
            <div>
              <Label htmlFor="s-new">New password</Label>
              <Input id="s-new" type="password" autoComplete="new-password" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} className="mt-1 bg-card" />
              <p className="mt-1 text-xs text-slate">At least 10 characters, mixing letters with numbers or symbols.</p>
            </div>
            <Button type="submit" variant="outline" disabled={!pw.current || !pw.next || password.isPending}>
              Change password
            </Button>
          </form>
        </Section>
      </div>

      <Section title="Sessions and account">
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rule pb-5">
            <p className="text-sm text-slate">Sign out of Prophecy on every device, including this one.</p>
            <Button variant="outline" onClick={() => everywhere.mutate()}>
              Sign out everywhere
            </Button>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (confirm("Permanently delete your account and all your properties, analyses and reports?")) del.mutate();
            }}
            className="flex flex-wrap items-end justify-between gap-3"
          >
            <div className="max-w-md">
              <p className="text-sm font-semibold text-brick">Delete account</p>
              <p className="text-sm text-slate">Removes your account and everything in it. This can&apos;t be undone.</p>
              <Input
                aria-label="Confirm with your password"
                type="password"
                placeholder="Your password"
                value={deletePw}
                onChange={(e) => setDeletePw(e.target.value)}
                className="mt-2 w-64 bg-card"
              />
            </div>
            <Button type="submit" variant="destructive" disabled={!deletePw || del.isPending}>
              Delete my account
            </Button>
          </form>
        </div>
      </Section>
    </>
  );
}
