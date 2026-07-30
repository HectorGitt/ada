"use client";

import { Check, Loader2, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { EmployerShell } from "@/components/hire/shell";
import { Button, Card, PageHeader, Skeleton } from "@/components/ui";
import {
  ApiError,
  api,
  type EmployerPlan,
  type Plan,
  type SubscriptionState,
} from "@/lib/api";

type Cadence = "monthly" | "annual";
type Provider = "paystack" | "stripe";

function money(plan: Plan, cadence: Cadence, provider: Provider): string {
  const price = plan[cadence];
  if (provider === "paystack") return `₦${(price.ngn_kobo / 100).toLocaleString()}`;
  return `$${(price.usd_cents / 100).toLocaleString()}`;
}

export default function EmployerBillingPage() {
  return (
    <EmployerShell>
      <EmployerBilling />
    </EmployerShell>
  );
}

function EmployerBilling() {
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [sub, setSub] = useState<SubscriptionState | null>(null);
  const [plan, setPlan] = useState<EmployerPlan | null>(null);
  const [cadence, setCadence] = useState<Cadence>("monthly");
  const [provider, setProvider] = useState<Provider>("paystack");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.employerPlans().then(setPlans).catch(() => setPlans([]));
    api.getSubscription().then(setSub).catch(() => setSub(null));
    api.employerPlan().then(setPlan).catch(() => setPlan(null));
  }, []);

  const subscribe = async (tier: string) => {
    setBusy(tier);
    setError("");
    try {
      const { checkout_url } = await api.startSubscription(tier, cadence, provider);
      window.location.href = checkout_url;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start checkout.");
      setBusy("");
    }
  };

  const cancel = async () => {
    if (!confirm("Cancel your plan? You keep access until the period ends.")) return;
    setBusy("cancel");
    try {
      await api.cancelSubscription();
      setSub(await api.getSubscription());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't cancel.");
    } finally {
      setBusy("");
    }
  };

  const current = plan?.tier ?? "pilot";
  const paid = current === "growth" || current === "scale";

  return (
    <>
      <PageHeader
        title="Plans & billing."
        subtitle="Post free on Pilot; go unlimited when hiring picks up. Every plan reads only candidates who opted in."
      />

      {plan && (
        <Card className="mb-6 flex flex-wrap items-center justify-between gap-3 border-accent/30 bg-accent-soft/40 px-6 py-4">
          <p className="text-sm">
            You&apos;re on <strong className="capitalize">{current}</strong>. Using{" "}
            <strong>{plan.roles_used}</strong>
            {plan.max_roles !== null ? ` / ${plan.max_roles}` : ""} role
            {plan.roles_used === 1 ? "" : "s"} and <strong>{plan.intros_used}</strong>
            {plan.max_intros !== null ? ` / ${plan.max_intros}` : ""} intro
            {plan.intros_used === 1 ? "" : "s"}.
          </p>
          {paid && sub?.status !== "canceled" && (
            <Button variant="secondary" onClick={cancel} loading={busy === "cancel"}>
              Cancel plan
            </Button>
          )}
        </Card>
      )}

      <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div className="inline-flex rounded-full border border-line bg-surface p-1 text-sm">
          {(["monthly", "annual"] as Cadence[]).map((c) => (
            <button
              key={c}
              onClick={() => setCadence(c)}
              className={`rounded-full px-4 py-1.5 font-medium capitalize transition-colors ${
                cadence === c ? "bg-accent text-accent-ink" : "text-muted hover:text-ink"
              }`}
            >
              {c}
              {c === "annual" && <span className="ml-1 text-[10px] opacity-80">2 mo free</span>}
            </button>
          ))}
        </div>
        <div className="inline-flex rounded-full border border-line bg-surface p-1 text-sm">
          {(["paystack", "stripe"] as Provider[]).map((p) => (
            <button
              key={p}
              onClick={() => setProvider(p)}
              className={`rounded-full px-4 py-1.5 font-medium transition-colors ${
                provider === p ? "bg-ink text-bg" : "text-muted hover:text-ink"
              }`}
            >
              {p === "paystack" ? "Pay in ₦" : "Pay in $"}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="mb-4 text-sm text-danger">{error}</p>}

      {plans === null ? (
        <div className="grid gap-5 md:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Card key={i} className="p-6">
              <Skeleton className="h-6 w-24" />
              <Skeleton className="mt-4 h-9 w-32" />
            </Card>
          ))}
        </div>
      ) : (
        <div className="grid items-start gap-5 md:grid-cols-3">
          <Card className="p-6">
            <p className="display text-xl">Pilot</p>
            <p className="mt-1 text-sm text-muted">See Uche work on one role.</p>
            <p className="mt-5 display text-4xl">₦0</p>
            <ul className="mt-5 space-y-2.5 text-sm">
              {["1 open role", "Ranked shortlist with reasons", "1 candidate intro"].map((f) => (
                <li key={f} className="flex gap-2.5 text-muted">
                  <Check className="mt-0.5 size-4 shrink-0 text-accent" /> {f}
                </li>
              ))}
            </ul>
            <p className="mt-6 text-center text-xs text-muted">
              {current === "pilot" ? "Your current plan" : " "}
            </p>
          </Card>

          {plans.map((p) => {
            const isCurrent = current === p.tier;
            const featured = p.tier === "growth";
            return (
              <Card
                key={p.tier}
                className={`relative p-6 ${featured ? "border-accent shadow-lift" : ""}`}
              >
                {featured && (
                  <span className="absolute -top-3 left-6 inline-flex items-center gap-1 rounded-full bg-accent px-3 py-1 text-[11px] font-medium text-accent-ink">
                    <Sparkles className="size-3" /> Most popular
                  </span>
                )}
                <p className="display text-xl">{p.name}</p>
                <p className="mt-1 text-sm text-muted">{p.tagline}</p>
                <p className="mt-5 display text-4xl">
                  {money(p, cadence, provider)}
                  <span className="text-base text-muted">/{cadence === "annual" ? "yr" : "mo"}</span>
                </p>
                <ul className="mt-5 space-y-2.5 text-sm">
                  {p.features.map((f) => (
                    <li key={f} className="flex gap-2.5">
                      <Check className="mt-0.5 size-4 shrink-0 text-accent" /> {f}
                    </li>
                  ))}
                </ul>
                <Button
                  onClick={() => subscribe(p.tier)}
                  loading={busy === p.tier}
                  disabled={isCurrent}
                  variant={featured ? "primary" : "secondary"}
                  className="mt-6 w-full"
                >
                  {isCurrent ? "Current plan" : busy === p.tier ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    `Get ${p.name}`
                  )}
                </Button>
              </Card>
            );
          })}
        </div>
      )}
    </>
  );
}
