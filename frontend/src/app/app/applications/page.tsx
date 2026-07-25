"use client";

import { Send } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import {
  Button,
  Card,
  EmptyState,
  PageHeader,
  Skeleton,
  StatusBadge,
} from "@/components/ui";
import { api, type ApplicationSummary } from "@/lib/api";

const STATUS: Record<
  string,
  { label: string; tone: "neutral" | "accent" | "success" | "warn" | "danger"; pulse?: boolean }
> = {
  preparing: { label: "Ada is applying", tone: "accent", pulse: true },
  submitted: { label: "Submitted", tone: "success" },
  needs_attention: { label: "Needs your attention", tone: "warn" },
  failed: { label: "Failed — nothing sent", tone: "danger" },
};

export default function ApplicationsPage() {
  const [apps, setApps] = useState<ApplicationSummary[] | null>(null);

  useEffect(() => {
    let live = true;
    const load = () => api.listApplications().then((a) => live && setApps(a)).catch(() => live && setApps([]));
    void load();
    const timer = setInterval(() => {
      void load();
    }, 5000);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, []);

  return (
    <>
      <PageHeader
        title="Applications."
        subtitle="Every application Ada has made for you, and where each one stands."
      />
      {apps === null ? (
        <div className="space-y-3">
          {[0, 1].map((i) => (
            <Card key={i} className="px-5 py-4">
              <Skeleton className="h-4 w-56" />
              <Skeleton className="mt-2.5 h-3 w-32" />
            </Card>
          ))}
        </div>
      ) : apps.length === 0 ? (
        <EmptyState
          icon={<Send className="size-5" />}
          title="No applications yet"
          body="Open a completed run and hit Apply on any match — Ada fills and submits the employer's form for you."
          action={
            <Link href="/app/runs">
              <Button>View my runs</Button>
            </Link>
          }
        />
      ) : (
        <div className="space-y-3">
          {apps.map((app) => {
            const status = STATUS[app.status] ?? { label: app.status, tone: "neutral" as const };
            return (
              <Card key={app.id} className="px-5 py-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{app.title}</p>
                    <p className="mt-0.5 text-xs text-muted">
                      {app.company} · {app.location}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <StatusBadge tone={status.tone} pulse={status.pulse}>
                      {status.label}
                    </StatusBadge>
                    <span className="text-xs text-muted">
                      {new Date(app.created_at).toLocaleDateString(undefined, {
                        day: "numeric",
                        month: "short",
                      })}
                    </span>
                  </div>
                </div>
                {app.detail && app.status !== "submitted" && (
                  <p className="mt-2.5 rounded-lg bg-surface-2 px-3 py-2 text-xs leading-relaxed text-muted">
                    {app.detail}
                  </p>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </>
  );
}
