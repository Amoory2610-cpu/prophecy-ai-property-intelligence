import { Suspense } from "react";

import { LoadingRows } from "@/components/common";
import { AppShell } from "@/components/app-shell";

// The shell reads the URL (active nav item, redirects), so it renders inside Suspense
// as Cache Components requires for request-time data.
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-[1180px] px-8 py-10">
          <LoadingRows rows={6} />
        </div>
      }
    >
      <AppShell>{children}</AppShell>
    </Suspense>
  );
}
