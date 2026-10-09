import Link from "next/link";

/** Ordnance Survey benchmark ("crow's foot") mark: a level line above a broad arrow. */
export function BenchmarkMark({ className = "size-6" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
      <path d="M3 6.5h18" />
      <path d="M12 6.5V20" />
      <path d="M12 6.5 6 19" />
      <path d="M12 6.5 18 19" />
    </svg>
  );
}

export function Wordmark({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="inline-flex items-center gap-2 text-ink" aria-label="Prophecy AI home">
      <BenchmarkMark className="size-6 text-wood" />
      <span className="font-heading text-[1.15rem] font-semibold tracking-tight">Prophecy</span>
    </Link>
  );
}
