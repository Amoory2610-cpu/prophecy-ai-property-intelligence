"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useSyncExternalStore } from "react";

import { api } from "./api";
import type { User } from "./types";

const noop = () => () => {};

/** False during server render and hydration, true afterwards. */
export function useMounted() {
  return useSyncExternalStore(noop, () => true, () => false);
}

export function useMe() {
  const mounted = useMounted();
  const q = useQuery({ queryKey: ["me"], queryFn: () => api<User>("/auth/me"), retry: false, staleTime: 5 * 60_000 });
  // The server never has the user, so hide cached data until hydration completes.
  return { ...q, data: mounted ? q.data : undefined };
}

export function useSignOut() {
  const qc = useQueryClient();
  const router = useRouter();
  return async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    qc.clear();
    router.replace("/login");
  };
}
