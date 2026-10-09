"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Wordmark } from "@/components/brand";
import { Notice } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ user: User }>(`/auth/${mode}`, {
        method: "POST",
        body: mode === "login" ? { email, password } : { email, password, full_name: name },
      });
      qc.setQueryData(["me"], res.user);
      const next = params.get("next");
      router.replace(next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, "Something went wrong. Try again."));
      setBusy(false);
    }
  }

  const fieldError = (f: string) => error?.fieldErrors.find((e) => e.field === f)?.message;

  return (
    <div className="flex min-h-screen flex-col">
      <div className="px-4 py-5 sm:px-8">
        <Wordmark />
      </div>
      <div className="flex flex-1 items-start justify-center px-4 pt-10 sm:pt-20">
        <form onSubmit={submit} className="w-full max-w-sm" noValidate>
          <h1 className="text-3xl font-semibold text-ink">{mode === "login" ? "Sign in" : "Create your account"}</h1>
          <p className="mt-1.5 text-sm text-slate">
            {mode === "login" ? (
              <>
                New here?{" "}
                <Link href="/register" className="font-medium text-wood underline underline-offset-2">
                  Create an account
                </Link>
              </>
            ) : (
              <>
                Already registered?{" "}
                <Link href="/login" className="font-medium text-wood underline underline-offset-2">
                  Sign in
                </Link>
              </>
            )}
          </p>

          {error && !error.fieldErrors.length && (
            <Notice tone="error" className="mt-5">
              {error.summary}
            </Notice>
          )}

          <div className="mt-6 space-y-4">
            {mode === "register" && (
              <div>
                <Label htmlFor="name">Name (optional)</Label>
                <Input id="name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} className="mt-1.5 bg-card" />
              </div>
            )}
            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                aria-invalid={Boolean(fieldError("email"))}
                aria-describedby={fieldError("email") ? "email-err" : undefined}
                className="mt-1.5 bg-card"
              />
              {fieldError("email") && <p id="email-err" className="mt-1 text-xs text-brick">{fieldError("email")}</p>}
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                aria-invalid={Boolean(fieldError("password"))}
                aria-describedby="password-help"
                className="mt-1.5 bg-card"
              />
              <p id="password-help" className={`mt-1 text-xs ${fieldError("password") ? "text-brick" : "text-slate"}`}>
                {fieldError("password") ?? (mode === "register" ? "At least 10 characters, mixing letters with numbers or symbols." : "")}
              </p>
            </div>
          </div>
          <Button type="submit" disabled={busy} className="mt-6 h-10 w-full text-[15px]">
            {busy ? (mode === "login" ? "Signing in…" : "Creating account…") : mode === "login" ? "Sign in" : "Create account"}
          </Button>
        </form>
      </div>
    </div>
  );
}
