"use client";

import { Building2, Check, Inbox, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Button, Card, EmptyState, PageHeader, Skeleton, StatusBadge } from "@/components/ui";
import { api, type CandidateIntro } from "@/lib/api";

const STATUS: Record<string, { label: string; tone: "accent" | "success" | "danger" }> = {
  requested: { label: "Wants to connect", tone: "accent" },
  accepted: { label: "You accepted", tone: "success" },
  declined: { label: "You declined", tone: "danger" },
};

export default function IntrosPage() {
  const [intros, setIntros] = useState<CandidateIntro[] | null>(null);

  useEffect(() => {
    api.candidateIntros().then(setIntros).catch(() => setIntros([]));
  }, []);

  const respond = async (id: string, action: "accept" | "decline") => {
    setIntros((cur) =>
      cur?.map((i) => (i.id === id ? { ...i, status: action === "accept" ? "accepted" : "declined" } : i)) ?? cur,
    );
    try {
      await api.respondIntro(id, action);
    } catch {
      api.candidateIntros().then(setIntros).catch(() => {});
    }
  };

  return (
    <>
      <PageHeader
        title="Intros."
        subtitle="Employers who found you through Uche and want to talk. You're only here because you opted in — you decide who connects."
      />
      {intros === null ? (
        <div className="space-y-3">
          {[0, 1].map((i) => (
            <Card key={i} className="px-5 py-5">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="mt-2.5 h-3 w-32" />
            </Card>
          ))}
        </div>
      ) : intros.length === 0 ? (
        <EmptyState
          icon={<Inbox className="size-5" />}
          title="No intros yet"
          body="When an employer wants to connect, it shows up here. Turn on 'Let employers find me' on your profile to be discoverable."
          action={
            <Link href="/app/profile">
              <Button variant="secondary">Go to profile</Button>
            </Link>
          }
        />
      ) : (
        <div className="space-y-3">
          {intros.map((intro) => {
            const status = STATUS[intro.status] ?? { label: intro.status, tone: "accent" as const };
            return (
              <Card key={intro.id} className="p-5">
                <div className="flex items-start gap-4">
                  <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
                    <Building2 className="size-5" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium">{intro.company}</p>
                      <StatusBadge tone={status.tone}>{status.label}</StatusBadge>
                    </div>
                    <p className="mt-0.5 text-sm text-muted">
                      Hiring for <span className="text-ink">{intro.role_title}</span> ·{" "}
                      {intro.remote ? "Remote" : intro.location}
                    </p>
                    {intro.message && (
                      <p className="mt-2.5 rounded-lg bg-surface-2 px-3 py-2 text-sm leading-relaxed text-muted">
                        “{intro.message}”
                      </p>
                    )}
                    {intro.status === "requested" && (
                      <div className="mt-3.5 flex gap-2.5">
                        <Button
                          onClick={() => respond(intro.id, "accept")}
                          className="!px-4 !py-2 text-xs"
                        >
                          <Check className="size-3.5" /> Accept intro
                        </Button>
                        <Button
                          onClick={() => respond(intro.id, "decline")}
                          variant="secondary"
                          className="!px-4 !py-2 text-xs"
                        >
                          <X className="size-3.5" /> Decline
                        </Button>
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </>
  );
}
