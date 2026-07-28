"use client";

import { Check, Loader2, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { Button, Card, PageHeader, Skeleton } from "@/components/ui";
import { ApiError, api, type Plan, type SubscriptionState } from "@/lib/api";

type Cadence = "monthly" | "annual";
type Provider = "paystack" | "stripe";

function money(plan: Plan, cadence: Cadence, provider: Provider): string {
  const price = plan[cadence];
  if (provider === "paystack") return `₦${(price.ngn_kobo / 100).toLocaleString()}`;
  return `$${(price.usd_cents / 100).toLocaleString()}`;
}

export default function BillingPage() {
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [sub, setSub] = useState<SubscriptionState | null>(null);
  const [cadence, setCadence] = useState<Cadence>("monthly");
  const [provider, setProvider] = useState<Provider>("paystack");
  const [busy, setBusy] = useState<string>("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.getPlans().then(setPlans).catch(() => setPlans([]));
    api.getSubscription().then(setSub).catch(() => setSub(null));
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
    if (!confirm("Cancel your subscription? You keep access until the period ends.")) return;
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

  const current = sub?.tier ?? "free";
  const isPaid = current === "pro" || current === "premium";

  return (
    <>
      <PageHeader
        title="Plans & billing."
        subtitle="Upgrade for unlimited runs, one-click apply, and live voice with Ada."
      />

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

      {sub && isPaid && (
        <Card className="mb-6 flex flex-wrap items-center justify-between gap-3 border-accent/30 bg-accent-soft/50 px-6 py-4">
          <p className="text-sm">
            You&apos;re on <strong className="capitalize">{current}</strong>
            {sub.status === "canceled" ? " — ending soon." : "."}{" "}
            {sub.current_period_end && (
              <span className="text-muted">
                Renews {new Date(sub.current_period_end).toLocaleDateString()}.
              </span>
            )}
          </p>
          {sub.status !== "canceled" && (
            <Button variant="secondary" onClick={cancel} loading={busy === "cancel"}>
              Cancel plan
            </Button>
          )}
        </Card>
      )}

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
            <p className="display text-xl">Free</p>
            <p className="mt-1 text-sm text-muted">Try Ada, pay per run.</p>
            <p className="mt-5 display text-4xl">₦0</p>
            <ul className="mt-5 space-y-2.5 text-sm">
              {["Browse every job", "One-off run purchase", "Your profile & documents"].map((f) => (
                <li key={f} className="flex gap-2.5 text-muted">
                  <Check className="mt-0.5 size-4 shrink-0 text-accent" /> {f}
                </li>
              ))}
            </ul>
            <p className="mt-6 text-center text-xs text-muted">
              {current === "free" ? "Your current plan" : " "}
            </p>
          </Card>

          {plans.map((plan) => {
            const isCurrent = current === plan.tier;
            const featured = plan.tier === "pro";
            return (
              <Card
                key={plan.tier}
                className={`relative p-6 ${featured ? "border-accent shadow-lift" : ""}`}
              >
                {featured && (
                  <span className="absolute -top-3 left-6 inline-flex items-center gap-1 rounded-full bg-accent px-3 py-1 text-[11px] font-medium text-accent-ink">
                    <Sparkles className="size-3" /> Most popular
                  </span>
                )}
                <p className="display text-xl">{plan.name}</p>
                <p className="mt-1 text-sm text-muted">{plan.tagline}</p>
                <p className="mt-5 display text-4xl">
                  {money(plan, cadence, provider)}
                  <span className="text-base text-muted">/{cadence === "annual" ? "yr" : "mo"}</span>
                </p>
                <ul className="mt-5 space-y-2.5 text-sm">
                  {plan.features.map((f) => (
                    <li key={f} className="flex gap-2.5">
                      <Check className="mt-0.5 size-4 shrink-0 text-accent" /> {f}
                    </li>
                  ))}
                </ul>
                <Button
                  onClick={() => subscribe(plan.tier)}
                  loading={busy === plan.tier}
                  disabled={isCurrent}
                  variant={featured ? "primary" : "secondary"}
                  className="mt-6 w-full"
                >
                  {isCurrent ? (
                    "Current plan"
                  ) : busy === plan.tier ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    `Get ${plan.name}`
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
