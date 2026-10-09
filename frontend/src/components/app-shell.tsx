"use client";

import {
  BarChart3,
  Building2,
  Database,
  FileText,
  GitCompareArrows,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Menu,
  Settings,
  SlidersHorizontal,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Wordmark } from "@/components/brand";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { ApiError } from "@/lib/api";
import { useMe, useSignOut } from "@/lib/session";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/properties", label: "Properties", icon: Building2 },
  { href: "/simulator", label: "Scenario simulator", icon: SlidersHorizontal },
  { href: "/compare", label: "Compare", icon: GitCompareArrows },
  { href: "/watchlists", label: "Watchlists", icon: ListChecks },
  { href: "/market", label: "Market data", icon: BarChart3 },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/data", label: "Data sources", icon: Database },
];

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="flex flex-col gap-0.5">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[14px] text-slate transition-colors hover:bg-muted hover:text-ink",
              active && "bg-card font-semibold text-ink shadow-[inset_2px_0_0_var(--wood)]",
            )}
          >
            <Icon className="size-4" aria-hidden />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

function AccountBlock() {
  const { data: me } = useMe();
  const signOut = useSignOut();
  return (
    <div className="border-t border-rule pt-3">
      <Link href="/settings" className="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[14px] text-slate hover:bg-muted hover:text-ink">
        <Settings className="size-4" aria-hidden />
        Account settings
      </Link>
      <button
        type="button"
        onClick={signOut}
        className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-[14px] text-slate hover:bg-muted hover:text-ink"
      >
        <LogOut className="size-4" aria-hidden />
        Sign out
      </button>
      {me && (
        <p className="truncate px-2.5 pt-2 text-xs text-slate" title={me.email}>
          {me.full_name || me.email}
        </p>
      )}
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { error } = useMe();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (error instanceof ApiError && error.status === 401) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [error, router, pathname]);

  return (
    <div className="flex min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-card focus:px-3 focus:py-2">
        Skip to content
      </a>
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col justify-between border-r border-rule px-3 py-5 lg:flex">
        <div>
          <div className="mb-6 px-2.5">
            <Wordmark href="/dashboard" />
          </div>
          <NavLinks />
        </div>
        <AccountBlock />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-rule px-4 py-3 lg:hidden">
          <Wordmark href="/dashboard" />
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger className="rounded-md p-2 text-ink hover:bg-muted" aria-label="Open menu">
              <Menu className="size-5" />
            </SheetTrigger>
            <SheetContent side="left" className="flex w-72 flex-col justify-between bg-paper p-4">
              <div>
                <SheetTitle className="mb-5">Menu</SheetTitle>
                <NavLinks onNavigate={() => setOpen(false)} />
              </div>
              <AccountBlock />
            </SheetContent>
          </Sheet>
        </div>
        <main id="main" className="mx-auto w-full max-w-[1180px] flex-1 px-4 py-8 sm:px-8 lg:py-10">
          {children}
        </main>
        <footer className="border-t border-rule px-4 py-4 text-xs text-slate sm:px-8">
          Prophecy produces estimates from your assumptions. It is not financial, tax or mortgage advice.
        </footer>
      </div>
    </div>
  );
}
