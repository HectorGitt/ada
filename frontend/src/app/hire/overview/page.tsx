"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { EmployerShell } from "@/components/hire/shell";
import { Button, Card, PageHeader, Skeleton } from "@/components/ui";
import { api, type EmployerOverview } from "@/lib/api";

const STAGES = ["shortlisted", "contacted", "interviewing", "offer", "hired"];

export default function OverviewPage() {
  return (
    <EmployerShell>
      <Overview />
    </EmployerShell>
  );
}

function Stat({ label, value, sub }: { label: string; value: number; sub?: string }) {
  return (
    <Card className="p-4">
      <p className="eyebrow !text-[10px]">{label}</p>
      <p className="display mt-1 text-3xl">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-muted">{sub}</p>}
    </Card>
  );
}

function Overview() {
  const [o, setO] = useState<EmployerOverview | null>(null);

  useEffect(() => {
    api.employerOverview().then(setO).catch(() => setO(null));
  }, []);

  return (
    <>
      <PageHeader title="Overview." subtitle="Your hiring at a glance — roles, outreach, and pipeline." />
      {!o ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Open roles" value={o.roles} />
            <Stat label="Intros sent" value={o.intros_sent} sub={`${o.intros_accepted} accepted`} />
            <Stat label="In pipeline" value={o.shortlist_total} />
            <Stat label="Hires" value={o.hires} />
          </div>

          <Card className="mt-4 p-5">
            <p className="eyebrow !text-[10px]">Pipeline</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {STAGES.map((s) => (
                <div key={s} className="min-w-[84px] flex-1 rounded-xl bg-surface-2 px-3 py-2.5 text-center">
                  <p className="display text-2xl leading-none">{o.shortlist_funnel[s] ?? 0}</p>
                  <p className="mt-1 text-[11px] capitalize text-muted">{s}</p>
                </div>
              ))}
            </div>
          </Card>

          {o.roles === 0 && (
            <Card className="mt-4 flex flex-wrap items-center justify-between gap-3 p-5">
              <p className="text-sm text-muted">Post your first role to start finding candidates.</p>
              <Link href="/hire">
                <Button>Post a role</Button>
              </Link>
            </Card>
          )}
        </>
      )}
    </>
  );
}
