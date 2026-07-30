"use client";

import { ArrowRight, Check } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui";

type Cadence = "monthly" | "annual";

type Tier = {
  name: string;
  tagline: string;
  ngn: Record<Cadence, string>;
  usd: Record<Cadence, string>;
  period: Record<Cadence, string>;
  features: string[];
  cta: string;
  featured?: boolean;
};

const TIERS: Tier[] = [
  {
    name: "Pilot",
    tagline: "See Uche work on one role.",
    ngn: { monthly: "₦0", annual: "₦0" },
    usd: { monthly: "$0", annual: "$0" },
    period: { monthly: "free", annual: "free" },
    features: ["1 open role", "Ranked shortlist with reasons", "1 candidate intro"],
    cta: "Post a role free",
  },
  {
    name: "Growth",
    tagline: "Hire on repeat, without the admin.",
    ngn: { monthly: "₦75,000", annual: "₦750,000" },
    usd: { monthly: "$149", annual: "$1,490" },
    period: { monthly: "/ month", annual: "/ year" },
    features: [
      "Unlimited roles & full shortlists",
      "Unlimited candidate intros",
      "Interview questions drafted per candidate",
      "Weekly best-fit candidate digest",
    ],
    cta: "Start hiring",
    featured: true,
  },
  {
    name: "Scale",
    tagline: "For teams hiring across roles.",
    ngn: { monthly: "₦200,000", annual: "₦2,000,000" },
    usd: { monthly: "$399", annual: "$3,990" },
    period: { monthly: "/ month", annual: "/ year" },
    features: [
      "Everything in Growth",
      "Priority curation & multiple seats",
      "Placement support on key hires",
      "Dedicated success manager",
    ],
    cta: "Talk to us",
  },
];

export function UchePricing() {
  const [cadence, setCadence] = useState<Cadence>("monthly");

  return (
    <section id="pricing" className="border-t border-line px-5 py-24">
      <div className="mx-auto max-w-6xl">
        <div className="mb-12 flex flex-col items-start gap-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="eyebrow mb-3">Pricing</p>
            <h2 className="display max-w-xl text-3xl leading-tight sm:text-4xl">
              Cheaper than one bad hire.
            </h2>
            <p className="mt-3 max-w-md text-muted">
              Post free, hire on a plan. A recruiter charges 15–20% of salary per role —
              Uche is a flat monthly fee across every role you&apos;re filling.
            </p>
          </div>
          <div className="inline-flex shrink-0 rounded-full border border-line bg-surface p-1 text-sm shadow-card">
            {(["monthly", "annual"] as Cadence[]).map((c) => (
              <button
                key={c}
                onClick={() => setCadence(c)}
                className={`rounded-full px-4 py-1.5 font-medium capitalize transition-colors ${
                  cadence === c ? "bg-ink text-bg" : "text-muted hover:text-ink"
                }`}
              >
                {c}
                {c === "annual" && <span className="ml-1.5 text-[10px] text-accent">2 months free</span>}
              </button>
            ))}
          </div>
        </div>

        <div className="grid items-stretch gap-5 lg:grid-cols-3">
          {TIERS.map((tier) => (
            <div
              key={tier.name}
              className={`relative flex flex-col rounded-card border p-7 transition-transform duration-300 hover:-translate-y-1 ${
                tier.featured
                  ? "border-accent bg-surface shadow-lift lg:-my-3 lg:py-10"
                  : "border-line bg-surface/60 shadow-card"
              }`}
            >
              {tier.featured && (
                <span className="absolute -top-3 left-7 rounded-full bg-accent px-3 py-1 text-[11px] font-medium text-accent-ink">
                  Most popular
                </span>
              )}
              <p className="display text-2xl">{tier.name}</p>
              <p className="mt-1 text-sm text-muted">{tier.tagline}</p>
              <div className="mt-6 flex items-baseline gap-2">
                <span className="display text-5xl">{tier.ngn[cadence]}</span>
                <span className="text-sm text-muted">
                  {tier.usd[cadence]} · {tier.period[cadence]}
                </span>
              </div>
              <ul className="mt-7 flex-1 space-y-3 text-sm">
                {tier.features.map((f) => (
                  <li key={f} className="flex gap-2.5">
                    <Check className="mt-0.5 size-4 shrink-0 text-accent" />
                    <span className={tier.featured ? "" : "text-muted"}>{f}</span>
                  </li>
                ))}
              </ul>
              <Link
                href={tier.name === "Pilot" ? "/hire" : "/hire/billing"}
                className="mt-8 block"
              >
                <Button
                  variant={tier.featured ? "primary" : "secondary"}
                  className="group w-full !py-3"
                >
                  {tier.cta}
                  <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
                </Button>
              </Link>
            </div>
          ))}
        </div>
        <p className="mt-8 text-center text-xs text-muted">
          Every plan reads only candidates who opted in to be found · Cancel anytime
        </p>
      </div>
    </section>
  );
}
