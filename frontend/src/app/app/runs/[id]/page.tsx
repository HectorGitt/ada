"use client";

import {
  ArrowRight,
  Check,
  Copy,
  Download,
  FileDown,
  MessageSquareText,
} from "lucide-react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";

import { ApplyButton } from "@/components/run/apply-button";
import { RunProgress } from "@/components/run/progress";
import { Button, Card, PageHeader, ScoreBar, SectionTitle, Skeleton } from "@/components/ui";
import { api, type RunResult } from "@/lib/api";

function RunSkeleton() {
  return (
    <div>
      <Skeleton className="h-9 w-64" />
      <Skeleton className="mt-3 h-4 w-44" />
      <Card className="mt-8 space-y-3 p-6">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
        <Skeleton className="h-4 w-4/6" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/6" />
      </Card>
    </div>
  );
}

function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const params = useSearchParams();
  const [run, setRun] = useState<RunResult | null>(null);
  const [missing, setMissing] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api
      .getRun(id)
      .then(setRun)
      .catch(() => setMissing(true));
  }, [id]);

  if (missing) return <p className="text-sm text-muted">Run not found.</p>;
  if (!run) return <RunSkeleton />;

  // Arrived from Stripe success or still executing: show live progress.
  if (run.status !== "complete" && run.status !== "failed") {
    return (
      <>
        <h1 className="display mb-6 text-3xl">
          {params.get("paid") ? "Payment received." : "In progress."}
        </h1>
        <RunProgress runId={id} />
      </>
    );
  }

  if (run.status === "failed") {
    return (
      <Card className="p-6">
        <p className="font-medium text-danger">This run failed.</p>
        <p className="mt-1 text-sm text-muted">You were not charged for it.</p>
      </Card>
    );
  }

  const copyCv = async () => {
    await navigator.clipboard.writeText(run.rewritten_cv ?? "");
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const downloadCv = () => {
    const blob = new Blob([run.rewritten_cv ?? ""], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ada-cv-${run.target_role.toLowerCase().replace(/\s+/g, "-")}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const stats: [string, string][] = [];
  if (run.matches?.length) stats.push([String(run.matches.length), "matches found"]);
  if (run.matches?.[0]) stats.push([`${run.matches[0].match}%`, "top match"]);
  if (run.questions?.length) stats.push([String(run.questions.length), "questions"]);
  if (run.interview) stats.push([`${run.interview.overall_score}/10`, "interview score"]);

  return (
    <>
      <PageHeader
        title={`${run.target_role}.`}
        subtitle="Your complete run — CV, matches, interview."
      />

      {stats.length > 0 && (
        <Card className="mb-10 flex divide-x divide-line overflow-x-auto quiet-scroll">
          {stats.map(([value, label]) => (
            <div key={label} className="min-w-28 flex-1 px-5 py-4">
              <p className="display text-2xl">{value}</p>
              <p className="mt-1 whitespace-nowrap text-xs text-muted">{label}</p>
            </div>
          ))}
        </Card>
      )}

      <section className="mb-10">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2.5">
          <SectionTitle>ATS-optimised CV</SectionTitle>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={copyCv} className="!px-3 !py-1.5 text-xs">
              {copied ? (
                <Check className="size-3.5 text-success" />
              ) : (
                <Copy className="size-3.5" />
              )}
              {copied ? "Copied" : "Copy"}
            </Button>
            <Button
              variant="secondary"
              onClick={downloadCv}
              className="!px-3 !py-1.5 text-xs"
            >
              <Download className="size-3.5" /> Markdown
            </Button>
            <Button
              onClick={() => window.open(`/print/run/${id}`, "_blank", "noopener")}
              className="!px-3 !py-1.5 text-xs"
            >
              <FileDown className="size-3.5" /> Save PDF
            </Button>
          </div>
        </div>
        <Card className="prose-ada max-h-[32rem] overflow-y-auto p-6 quiet-scroll sm:p-8">
          <ReactMarkdown>{run.rewritten_cv ?? ""}</ReactMarkdown>
        </Card>
      </section>

      {run.matches && run.matches.length > 0 && (
        <section className="mb-10">
          <div className="mb-3">
            <SectionTitle>Best-fit roles</SectionTitle>
          </div>
          <div className="space-y-3">
            {run.matches.map((m, i) => (
              <Card key={i} hover className="px-5 py-4">
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-[10px] border border-line bg-surface-2 text-xs font-semibold text-muted">
                    {m.company.slice(0, 2)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-4">
                      <div className="min-w-0">
                        <p className="truncate font-medium">{m.title}</p>
                        <p className="mt-0.5 text-xs text-muted">
                          {m.company} · {m.location}
                        </p>
                      </div>
                      <span className="display text-2xl text-accent">{m.match}%</span>
                    </div>
                    <div className="mt-3">
                      <ScoreBar value={m.match} />
                    </div>
                    <p className="mt-2.5 text-xs leading-relaxed text-muted">{m.reason}</p>
                    <div className="mt-3 flex justify-end">
                      {typeof m.job_id === "number" && <ApplyButton jobId={m.job_id} runId={id} />}
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </section>
      )}

      {run.questions && run.questions.length > 0 && (
        <section>
          <div className="mb-3">
            <SectionTitle>Mock interview</SectionTitle>
          </div>
          <Card className="p-6">
            {run.interview ? (
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                  <span className="display text-4xl text-accent">
                    {run.interview.overall_score}
                    <span className="text-lg text-muted">/10</span>
                  </span>
                  <div>
                    <p className="font-medium">Interview scored</p>
                    <p className="text-sm text-muted">
                      View your question-by-question feedback.
                    </p>
                  </div>
                </div>
                <Link href={`/app/runs/${id}/interview`}>
                  <Button variant="secondary">Review feedback</Button>
                </Link>
              </div>
            ) : (
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <p className="font-medium">
                    {run.questions.length} questions tailored to this role
                  </p>
                  <p className="text-sm text-muted">
                    Answer them and Ada scores you with specific feedback.
                  </p>
                </div>
                <Link href={`/app/runs/${id}/interview`}>
                  <Button>
                    <MessageSquareText className="size-4" /> Take the interview
                  </Button>
                </Link>
              </div>
            )}
          </Card>
        </section>
      )}

      {/* Mobile: the next step floats above the tab bar on a paper fade
          (per the mobile design canvas) */}
      {run.questions && run.questions.length > 0 && !run.interview && (
        <div className="pointer-events-none fixed inset-x-0 bottom-0 z-10 bg-gradient-to-t from-bg via-bg/85 to-transparent px-5 pb-28 pt-12 lg:hidden">
          <Link
            href={`/app/runs/${id}/interview`}
            className="pointer-events-auto block"
          >
            <Button className="w-full !py-3.5">
              Take the mock interview <ArrowRight className="size-4" />
            </Button>
          </Link>
        </div>
      )}
    </>
  );
}

export default function RunDetailPage() {
  return (
    <Suspense>
      <RunDetail />
    </Suspense>
  );
}
