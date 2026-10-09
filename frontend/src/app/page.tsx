import Link from "next/link";

import { Wordmark } from "@/components/brand";
import { QuickEstimate } from "@/components/quick-estimate";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const CAPABILITIES = [
  {
    title: "Every figure shows its working",
    body: "Yields, cash flow, stamp duty, mortgage payments and returns each come with the formula and the exact inputs used. Estimates that depend on tax rules or growth assumptions are labelled as estimates.",
  },
  {
    title: "Stress-test before you offer",
    body: "Move the rate, rent, voids and price and watch cash flow respond. Base, optimistic and pessimistic cases show which assumption is doing the damage, and break-even figures tell you what would have to change.",
  },
  {
    title: "Real sale prices, not guesses",
    body: "Comparable sales and area statistics come from HM Land Registry Price Paid Data that you import, with the source, licence and date range shown alongside every chart.",
  },
  {
    title: "Compare on equal terms",
    body: "Put up to six properties through the same financing and cost assumptions, see where each one leads and lags, and export the comparison as CSV.",
  },
];

export default function Landing() {
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-[1180px] items-center justify-between px-4 py-5 sm:px-8">
        <Wordmark />
        <nav className="flex items-center gap-2">
          <Link href="/login" className={buttonVariants({ variant: "ghost" })}>
            Sign in
          </Link>
          <Link href="/register" className={buttonVariants()}>
            Create account
          </Link>
        </nav>
      </header>

      <main>
        <section className="mx-auto grid max-w-[1180px] items-start gap-10 px-4 pb-16 pt-8 sm:px-8 lg:grid-cols-[1fr_minmax(0,520px)] lg:gap-14 lg:pt-16">
          <div className="max-w-xl">
            <h1 className="text-[2.6rem] font-semibold leading-[1.05] tracking-[-0.02em] text-ink sm:text-[3.4rem]">
              Know what a buy-to-let deal really returns before you make an offer.
            </h1>
            <p className="mt-5 text-lg leading-relaxed text-slate">
              Enter a price and a rent. Prophecy works out stamp duty, the mortgage, void periods and running costs
              for UK rental property, and shows the working for every number.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link href="/register" className={cn(buttonVariants({ size: "lg" }), "h-11 px-5 text-[15px]")}>
                Analyse a property
              </Link>
              <Link href="/login" className={cn(buttonVariants({ variant: "outline", size: "lg" }), "h-11 px-5 text-[15px]")}>
                I have an account
              </Link>
            </div>
            <p className="mt-6 max-w-md text-sm leading-relaxed text-slate">
              Figures are estimates based on your assumptions and published tax rates. They are not financial, tax
              or mortgage advice.
            </p>
          </div>
          <QuickEstimate />
        </section>

        <section className="border-t border-rule bg-card">
          <div className="mx-auto grid max-w-[1180px] gap-x-12 gap-y-10 px-4 py-14 sm:px-8 md:grid-cols-2">
            {CAPABILITIES.map((c) => (
              <div key={c.title} className="max-w-lg">
                <h2 className="text-xl font-semibold text-ink">{c.title}</h2>
                <p className="mt-2 leading-relaxed text-slate">{c.body}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-[1180px] px-4 py-14 sm:px-8">
          <div className="grid gap-8 md:grid-cols-[1fr_1fr]">
            <div>
              <h2 className="text-2xl font-semibold text-ink">What it covers, and what it doesn&apos;t</h2>
              <p className="mt-3 leading-relaxed text-slate">
                Stamp Duty Land Tax for England and Northern Ireland, LBTT for Scotland and LTT for Wales, including
                the additional-dwelling surcharges. Section 24 mortgage interest rules and company ownership are
                modelled as simplified scenarios.
              </p>
            </div>
            <ul className="space-y-2 text-[15px] leading-relaxed text-ink">
              <li className="border-b border-rule pb-2">Rents, costs and growth rates are your assumptions, never presented as market facts.</li>
              <li className="border-b border-rule pb-2">Market statistics only appear when real Land Registry data has been imported.</li>
              <li className="border-b border-rule pb-2">AI explanations are grounded in the calculated figures, and any number that can&apos;t be traced is flagged.</li>
              <li>Tax rules are dated and linked to their official sources so you can check them.</li>
            </ul>
          </div>
        </section>
      </main>

      <footer className="border-t border-rule">
        <div className="mx-auto flex max-w-[1180px] flex-wrap justify-between gap-3 px-4 py-6 text-xs text-slate sm:px-8">
          <p>Prophecy AI. A property investment analysis tool for the UK market.</p>
          <p>Contains HM Land Registry data © Crown copyright and database right, licensed under the OGL v3.0, where imported.</p>
        </div>
      </footer>
    </div>
  );
}
