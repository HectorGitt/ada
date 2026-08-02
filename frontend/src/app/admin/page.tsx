"use client";

import { useEffect, useState } from "react";

import { Card, Skeleton } from "@/components/ui";
import { api, type AdminOverview } from "@/lib/api";

function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <Card className="p-4">
      <p className="eyebrow !text-[10px]">{label}</p>
      <p className="display mt-1 text-3xl">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-muted">{sub}</p>}
    </Card>
  );
}

function Breakdown({ label, data }: { label: string; data: Record<string, number> }) {
  const entries = Object.entries(data);
  return (
    <Card className="p-4">
      <p className="eyebrow !text-[10px]">{label}</p>
      <div className="mt-2 space-y-1.5">
        {entries.length === 0 ? (
          <p className="text-xs text-muted">None yet.</p>
        ) : (
          entries.map(([k, v]) => (
            <div key={k} className="flex items-center justify-between text-sm">
              <span className="capitalize text-muted">{k.replace(/_/g, " ")}</span>
              <span className="font-medium tabular-nums">{v}</span>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}

const money = (minor: number, ccy: string) => {
  const major = minor / 100;
  return `${ccy} ${major.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
};

export default function AdminOverviewPage() {
  const [o, setO] = useState<AdminOverview | null>(null);

  useEffect(() => {
    api.admin.overview().then(setO).catch(() => setO(null));
  }, []);

  if (!o) {
    return (
      <>
        <h1 className="display mb-6 text-3xl">Overview.</h1>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      </>
    );
  }

  return (
    <>
      <h1 className="display mb-6 text-3xl">Overview.</h1>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat
          label="Users"
          value={o.users_total}
          sub={`${o.users_by_type.candidate ?? 0} candidates · ${o.users_by_type.employer ?? 0} employers`}
        />
        <Stat label="Runs" value={o.runs_total} sub={`${o.runs_by_status.complete ?? 0} complete`} />
        <Stat
          label="Active plans"
          value={o.subscriptions_active}
          sub={Object.entries(o.subscriptions_by_tier).map(([t, n]) => `${n} ${t}`).join(" · ") || "none"}
        />
        <Stat
          label="Jobs"
          value={o.jobs_total.toLocaleString()}
          sub={`${o.jobs_embedded.toLocaleString()} embedded`}
        />
        <Stat label="Applications" value={o.applications_total} sub={`${o.applications_submitted} submitted`} />
        <Stat label="Intros" value={o.intros_total} sub={`${o.intros_accepted} accepted`} />
        <Stat label="Identity verified" value={o.identity_verified} />
        <Stat label="Assessments passed" value={o.assessments_verified} />
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <Breakdown label="Runs by status" data={o.runs_by_status} />
        <Breakdown label="Plans by tier" data={o.subscriptions_by_tier} />
        <Card className="p-4">
          <p className="eyebrow !text-[10px]">Revenue (paid runs)</p>
          <div className="mt-2 space-y-1.5">
            {o.revenue.length === 0 ? (
              <p className="text-xs text-muted">No paid runs yet.</p>
            ) : (
              o.revenue.map((r) => (
                <div key={r.currency} className="flex items-center justify-between text-sm">
                  <span className="text-muted">{r.runs} runs</span>
                  <span className="font-medium tabular-nums">{money(r.amount_minor, r.currency)}</span>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>
    </>
  );
}
