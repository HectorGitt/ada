"use client";

import { Send } from "lucide-react";
import { useEffect, useState } from "react";

import { EmployerShell } from "@/components/hire/shell";
import { Card, EmptyState, PageHeader, Skeleton, StatusBadge } from "@/components/ui";
import { IntroThread } from "@/components/intro-thread";
import { api, type EmployerIntro } from "@/lib/api";

const STATUS: Record<string, { label: string; tone: "accent" | "success" | "danger" }> = {
  requested: { label: "Requested", tone: "accent" },
  accepted: { label: "Accepted", tone: "success" },
  declined: { label: "Declined", tone: "danger" },
};

export default function IntrosPage() {
  return (
    <EmployerShell>
      <IntrosInbox />
    </EmployerShell>
  );
}

function IntrosInbox() {
  const [intros, setIntros] = useState<EmployerIntro[] | null>(null);

  useEffect(() => {
    api.employerIntros().then(setIntros).catch(() => setIntros([]));
  }, []);

  return (
    <>
      <PageHeader
        title="Intros."
        subtitle="Every candidate you've reached out to — and where each conversation stands."
      />
      {intros === null ? (
        <div className="space-y-3">
          {[0, 1].map((i) => (
            <Card key={i} className="px-5 py-4">
              <Skeleton className="h-4 w-52" />
              <Skeleton className="mt-2.5 h-3 w-28" />
            </Card>
          ))}
        </div>
      ) : intros.length === 0 ? (
        <EmptyState
          icon={<Send className="size-5" />}
          title="No intros yet"
          body="Open a role, review Uche's shortlist, and request an intro to reach a candidate."
        />
      ) : (
        <div className="space-y-3">
          {intros.map((intro) => {
            const status = STATUS[intro.status] ?? { label: intro.status, tone: "accent" as const };
            return (
              <Card key={intro.id} className="px-5 py-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-medium">
                      {intro.candidate_headline ?? "Candidate"}
                    </p>
                    <p className="mt-0.5 text-xs text-muted">
                      Requested{" "}
                      {new Date(intro.created_at).toLocaleDateString(undefined, {
                        day: "numeric",
                        month: "short",
                      })}
                    </p>
                  </div>
                  <StatusBadge tone={status.tone}>{status.label}</StatusBadge>
                </div>
                {intro.message && (
                  <p className="mt-2.5 rounded-lg bg-surface-2 px-3 py-2 text-xs leading-relaxed text-muted">
                    {intro.message}
                  </p>
                )}
                {intro.status === "accepted" && (
                  <IntroThread
                    introId={intro.id}
                    me="employer"
                    fetchThread={api.employerIntroThread}
                    send={api.employerSendMessage}
                  />
                )}
              </Card>
            );
          })}
        </div>
      )}
    </>
  );
}
