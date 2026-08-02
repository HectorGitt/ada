"use client";

import {
  ArrowRight,
  ArrowUp,
  ArrowUpRight,
  FileText,
  Mic,
  Plus,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/app/shell";
import {
  Button,
  Card,
  ScoreBar,
  ScoreRing,
  SectionTitle,
  Skeleton,
  StatusBadge,
} from "@/components/ui";
import { api, RUN_STATUS, type RunResult, type RunSummary } from "@/lib/api";

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function firstName(email: string): string {
  const raw = email.split("@")[0].split(/[._\-+]/)[0] || "there";
  return raw.charAt(0).toUpperCase() + raw.slice(1);
}

const QUICK_LINKS = [
  { href: "/app/new", icon: Plus, title: "Start a new run", body: "CV rewrite, matches, interview prep" },
  { href: "/app/voice", icon: Mic, title: "Talk to Ada", body: "A quick conversation drafts the run for you" },
  { href: "/app/documents", icon: FileText, title: "Your documents", body: "Every CV Ada has written for you" },
];

export default function HomePage() {
  const { email } = useAuth();
  const router = useRouter();
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [latest, setLatest] = useState<
    { summary: RunSummary; result: RunResult } | null | undefined
  >(undefined);
  const [hasProfile, setHasProfile] = useState<boolean | null>(null);
  const [ask, setAsk] = useState("");

  useEffect(() => {
    api
      .listRuns()
      .then((rs) => {
        setRuns(rs);
        const done = rs.find((r) => r.status === "complete");
        if (!done) {
          setLatest(null);
          return;
        }
        api
          .getRun(done.run_id)
          .then((result) => setLatest({ summary: done, result }))
          .catch(() => setLatest(null));
      })
      .catch(() => {
        setRuns([]);
        setLatest(null);
      });
    // Only nudge when we're sure there's no profile.
    api.getProfile().then((p) => setHasProfile(p !== null)).catch(() => setHasProfile(true));
  }, []);

  const askAda = (e: React.FormEvent) => {
    e.preventDefault();
    const q = ask.trim();
    if (!q) return;
    // The coach page picks this up on mount and sends it immediately.
    localStorage.setItem("ada.coach-ask", q);
    router.push("/app/coach");
  };

  const completed = runs?.filter((r) => r.status === "complete").length ?? 0;
  const interviews = runs?.filter((r) => r.has_interview).length ?? 0;
  const topMatch = latest?.result.matches?.[0]?.match ?? null;
  const recent = runs?.slice(0, 4) ?? [];
  const today = new Date().toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  return (
    <>
      <div className="mb-10">
        <p className="eyebrow mb-3">{today}</p>
        <h1 className="display text-4xl sm:text-[2.75rem]">
          {greeting()}, {firstName(email)}.
        </h1>
        <p className="mt-3 text-sm text-muted">
          You&apos;re{" "}
          <em className="display text-[15px] italic text-accent">one run</em> from
          your next role.
        </p>
      </div>

      {/* Pulse of the account. Mobile: one segmented card with hairline
          dividers (per the mobile design canvas); larger screens: three cards. */}
      {runs === null ? (
        <div className="mb-6 grid grid-cols-3 gap-3 sm:gap-4">
          {[0, 1, 2].map((i) => (
            <Card key={i} className="p-5">
              <Skeleton className="h-9 w-14" />
              <Skeleton className="mt-2.5 h-3 w-20" />
            </Card>
          ))}
        </div>
      ) : (
        <>
          <Card className="mb-6 grid grid-cols-3 divide-x divide-line text-center sm:hidden">
            <div className="px-2 py-4">
              <p className="display text-3xl">{completed}</p>
              <p className="mt-1 text-[10px] text-muted">
                {completed === 1 ? "run" : "runs"}
              </p>
            </div>
            <div className="px-2 py-4">
              <p className="display text-3xl">{interviews}</p>
              <p className="mt-1 text-[10px] text-muted">
                {interviews === 1 ? "interview" : "interviews"}
              </p>
            </div>
            <div className="px-2 py-4">
              <p className={`display text-3xl ${topMatch !== null ? "text-accent" : "text-muted/60"}`}>
                {topMatch !== null ? `${topMatch}%` : "—"}
              </p>
              <p className="mt-1 text-[10px] text-muted">top match</p>
            </div>
          </Card>
          <div className="mb-6 hidden grid-cols-3 gap-4 sm:grid">
            <Card className="p-5">
              <p className="display text-4xl">{completed}</p>
              <p className="mt-1.5 text-xs text-muted">
                {completed === 1 ? "run completed" : "runs completed"}
              </p>
            </Card>
            <Card className="p-5">
              <p className="display text-4xl">{interviews}</p>
              <p className="mt-1.5 text-xs text-muted">
                {interviews === 1 ? "interview scored" : "interviews scored"}
              </p>
            </Card>
            <Card className="flex items-center justify-between gap-2 p-5">
              {topMatch !== null ? (
                <>
                  <div>
                    <p className="display text-4xl">{topMatch}%</p>
                    <p className="mt-1.5 text-xs text-muted">top match</p>
                  </div>
                  <ScoreRing value={topMatch} size={56} stroke={5} />
                </>
              ) : (
                <div>
                  <p className="display text-4xl text-muted/60">—</p>
                  <p className="mt-1.5 text-xs text-muted">top match</p>
                </div>
              )}
            </Card>
          </div>
        </>
      )}

      <div className="mb-6 grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        {/* Latest results, or the first-run invitation */}
        {latest === undefined ? (
          <Card className="space-y-4 p-6">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-7 w-56" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
          </Card>
        ) : latest ? (
          <Card className="flex flex-col p-6">
            <div className="mb-4 flex items-center justify-between">
              <p className="eyebrow !text-[10px]">Latest run</p>
              <StatusBadge tone="success">Complete</StatusBadge>
            </div>
            <h2 className="display mb-5 text-2xl">{latest.summary.target_role}.</h2>
            <div className="flex-1 space-y-3.5">
              {(latest.result.matches ?? []).slice(0, 3).map((m) => (
                <div key={`${m.title}-${m.company}`} className="flex items-center gap-2.5">
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-[10px] border border-line bg-surface-2 text-xs font-semibold text-muted">
                    {m.company.slice(0, 2)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-3">
                      <p className="min-w-0 truncate text-sm font-medium">
                        {m.title}{" "}
                        <span className="font-normal text-muted">· {m.company}</span>
                      </p>
                      <span className="display text-lg text-accent">{m.match}%</span>
                    </div>
                    <div className="mt-1">
                      <ScoreBar value={m.match} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-6 flex flex-wrap gap-2.5">
              <Link href={`/app/runs/${latest.summary.run_id}`}>
                <Button variant="secondary" className="!px-4 !py-2 text-xs">
                  View full run
                </Button>
              </Link>
              <Link href={`/app/runs/${latest.summary.run_id}/interview`}>
                <Button className="!px-4 !py-2 text-xs">
                  {latest.summary.has_interview ? "Review interview" : "Take the interview"}
                  <ArrowRight className="size-3.5" />
                </Button>
              </Link>
            </div>
          </Card>
        ) : (
          <Card className="relative overflow-hidden p-6 sm:p-8">
            <div
              className="absolute -right-16 -top-16 size-48 rounded-full bg-accent/10 blur-2xl"
              aria-hidden
            />
            <p className="eyebrow mb-3 !text-[10px]">First run</p>
            <h2 className="display text-3xl">
              Your next role starts with <em className="text-accent">one run</em>.
            </h2>
            <p className="mt-3 max-w-md text-sm leading-relaxed text-muted">
              Ada rewrites your CV for the role you want, ranks your best-fit jobs, and
              scores a mock interview — autonomously, in minutes.
            </p>
            <div className="mt-6 flex flex-wrap items-center gap-4">
              <Link href="/app/new">
                <Button className="group">
                  Start your first run
                  <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
                </Button>
              </Link>
              <Link
                href="/app/voice"
                className="text-sm text-muted underline-offset-4 hover:text-ink hover:underline"
              >
                or talk it through
              </Link>
            </div>
          </Card>
        )}

        {/* Quick actions + profile nudge */}
        <div className="flex flex-col gap-6">
          <Card className="divide-y divide-line">
            {QUICK_LINKS.map(({ href, icon: Icon, title, body }) => (
              <Link
                key={href}
                href={href}
                className="group flex items-center gap-3.5 px-5 py-4 transition-colors first:rounded-t-card last:rounded-b-card hover:bg-line/30"
              >
                <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
                  <Icon className="size-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium">{title}</span>
                  <span className="block truncate text-xs text-muted">{body}</span>
                </span>
                <ArrowUpRight className="size-4 shrink-0 text-muted transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
              </Link>
            ))}
          </Card>
          {hasProfile === false && (
            <Card className="border-accent/30 bg-accent-soft/60 p-5">
              <div className="flex items-start gap-3">
                <UserRound className="mt-0.5 size-4 shrink-0 text-accent" />
                <div>
                  <p className="text-sm font-medium">Teach Ada your background</p>
                  <p className="mt-1 text-xs leading-relaxed text-muted">
                    Import your LinkedIn profile once — every rewrite, match, and
                    conversation gets sharper.
                  </p>
                  <Link
                    href="/app/profile"
                    className="mt-2 inline-block text-xs font-medium text-accent underline-offset-2 hover:underline"
                  >
                    Set up your profile →
                  </Link>
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* Hand a question straight to the coach */}
      <Card className="mb-6 p-6">
        <h2 className="display text-xl">Ask Ada anything.</h2>
        <p className="mt-1 text-xs text-muted">
          Career advice grounded in your profile and your runs — not generic tips.
        </p>
        <form onSubmit={askAda} className="mt-4 flex items-center gap-2">
          <input
            value={ask}
            onChange={(e) => setAsk(e.target.value)}
            placeholder="Should I take a pay cut to switch industries?"
            className="w-full flex-1 rounded-full border border-line bg-bg px-4 py-2.5 text-sm outline-none transition-colors placeholder:text-muted/60 focus:border-accent"
          />
          <button
            type="submit"
            aria-label="Ask Ada"
            disabled={!ask.trim()}
            className="rounded-full bg-accent p-2.5 text-accent-ink shadow-btn transition-transform hover:scale-105 disabled:opacity-40 disabled:shadow-none"
          >
            <ArrowUp className="size-4" />
          </button>
        </form>
      </Card>

      {/* Recent runs */}
      {recent.length > 0 && (
        <section>
          <div className="mb-3 flex items-baseline justify-between">
            <SectionTitle>Recent runs</SectionTitle>
            <Link
              href="/app/runs"
              className="text-xs text-muted underline-offset-2 hover:text-ink hover:underline"
            >
              View all
            </Link>
          </div>
          <div className="space-y-2.5">
            {recent.map((run) => {
              const status = RUN_STATUS[run.status] ?? { label: run.status, tone: "neutral" as const };
              return (
                <Link key={run.run_id} href={`/app/runs/${run.run_id}`} className="group block">
                  <Card hover className="flex items-center justify-between gap-4 px-5 py-3.5">
                    <div className="flex min-w-0 items-center gap-3">
                      <p className="truncate text-sm font-medium">{run.target_role}</p>
                      <StatusBadge tone={status.tone} pulse={status.pulse}>
                        {status.label}
                      </StatusBadge>
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      <span className="text-xs text-muted">
                        {new Date(run.created_at).toLocaleDateString(undefined, {
                          day: "numeric",
                          month: "short",
                        })}
                      </span>
                      <ArrowUpRight className="size-4 text-muted transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
                    </div>
                  </Card>
                </Link>
              );
            })}
          </div>
        </section>
      )}
    </>
  );
}
