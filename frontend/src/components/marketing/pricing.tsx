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
  href: string;
  featured?: boolean;
  foot?: string;
};

const TIERS: Tier[] = [
  {
    name: "Free",
    tagline: "Try Ada, pay per run.",
    ngn: { monthly: "₦0", annual: "₦0" },
    usd: { monthly: "$0", annual: "$0" },
    period: { monthly: "forever", annual: "forever" },
    features: ["Browse every job", "One-off run — ₦2,000 / $9.99", "Your profile & documents"],
    cta: "Start free",
    href: "/app/new",
  },
  {
    name: "Pro",
    tagline: "Everything Ada does, unlimited.",
    ngn: { monthly: "₦5,000", annual: "₦50,000" },
    usd: { monthly: "$19", annual: "$190" },
    period: { monthly: "/ month", annual: "/ year" },
    features: [
      "Unlimited CV rewrites, matches & mock interviews",
      "One-click apply — Ada submits for you",
      "Ask Ada, grounded in your runs",
    ],
    cta: "Choose Pro",
    href: "/app/billing",
    featured: true,
  },
  {
    name: "Premium",
    tagline: "Your career, with Ada on call.",
    ngn: { monthly: "₦12,000", annual: "₦120,000" },
    usd: { monthly: "$39", annual: "$390" },
    period: { monthly: "/ month", annual: "/ year" },
    features: ["Everything in Pro", "Live voice coaching & interviews", "Priority + weekly job digest"],
    cta: "Choose Premium",
    href: "/app/billing",
  },
];

export function PricingTiers() {
  const [cadence, setCadence] = useState<Cadence>("monthly");

  return (
    <div>
      <div className="mb-12 flex flex-col items-start gap-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="display fluid-h2 mb-3">Start free. Scale when it&apos;s working.</h2>
          <p className="max-w-md text-muted">
            One run, one price — or go unlimited. A senior coach charges more for an hour
            than Ada charges for a month.
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
              {c === "annual" && (
                <span className="ml-1.5 text-[10px] text-accent">2 months free</span>
              )}
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
            <Link href={tier.href} className="mt-8 block">
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
        Paystack for Nigeria · Stripe worldwide · Cancel anytime · Results in under 3 minutes
      </p>
    </div>
  );
}
