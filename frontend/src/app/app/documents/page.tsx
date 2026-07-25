"use client";

import { ChevronDown, FileText, Loader2, Upload } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Button, Card, EmptyState, PageHeader, Skeleton } from "@/components/ui";
import { api, type RunSummary, type UploadedDoc } from "@/lib/api";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** One uploaded CV row with an expandable text preview, fetched on first open. */
function UploadedRow({ doc }: { doc: UploadedDoc }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && text === null && !failed) {
      api
        .getDocument(doc.id)
        .then((d) => setText(d.cv_text))
        .catch(() => setFailed(true));
    }
  };

  return (
    <div className="first:rounded-t-card last:rounded-b-card">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        className="group flex w-full items-center gap-3.5 px-4 py-3.5 text-left transition-colors hover:bg-line/30 sm:px-5"
      >
        <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-accent-soft">
          <Upload className="size-4 text-accent" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{doc.filename}</p>
          <p className="mt-0.5 text-xs text-muted">
            {formatDate(doc.created_at)} · {formatSize(doc.size_bytes)}
          </p>
        </div>
        <ChevronDown
          className={`size-4 shrink-0 text-muted transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div className="border-t border-line bg-line/10 px-4 py-4 sm:px-5">
          {failed ? (
            <p className="text-sm text-danger">Couldn&apos;t load the preview.</p>
          ) : text === null ? (
            <p className="inline-flex items-center gap-2 text-sm text-muted">
              <Loader2 className="size-3.5 animate-spin" /> Loading preview…
            </p>
          ) : (
            <pre className="max-h-80 overflow-y-auto whitespace-pre-wrap font-sans text-xs leading-relaxed text-muted">
              {text}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export default function DocumentsPage() {
  const [generated, setGenerated] = useState<RunSummary[] | null>(null);
  const [uploads, setUploads] = useState<UploadedDoc[] | null>(null);

  useEffect(() => {
    api
      .listRuns()
      .then((runs) => setGenerated(runs.filter((r) => r.status === "complete")))
      .catch(() => setGenerated([]));
    api
      .listDocuments()
      .then(setUploads)
      .catch(() => setUploads([]));
  }, []);

  const loading = generated === null || uploads === null;
  const empty = !loading && generated.length === 0 && uploads.length === 0;

  return (
    <>
      <PageHeader
        title="Documents."
        subtitle="CVs you've uploaded and every CV Ada has written for you."
      />
      {loading ? (
        <div className="space-y-3">
          {[0, 1].map((i) => (
            <Card key={i} className="px-5 py-4">
              <Skeleton className="h-4 w-56" />
              <Skeleton className="mt-2.5 h-3 w-24" />
            </Card>
          ))}
        </div>
      ) : empty ? (
        <EmptyState
          icon={<FileText className="size-5" />}
          title="No documents yet"
          body="Upload a CV when starting a run, and Ada's rewrites land here too."
          action={
            <Link href="/app/new">
              <Button>Start a run</Button>
            </Link>
          }
        />
      ) : (
        <div className="space-y-10">
          {uploads.length > 0 && (
            <section>
              <h2 className="eyebrow mb-3">Uploaded by you</h2>
              <Card className="divide-y divide-line overflow-hidden">
                {uploads.map((doc) => (
                  <UploadedRow key={doc.id} doc={doc} />
                ))}
              </Card>
            </section>
          )}
          {generated.length > 0 && (
            <section>
              <h2 className="eyebrow mb-3">Written by Ada</h2>
              <Card className="divide-y divide-line overflow-hidden">
                {generated.map((doc, i) => (
                  <Link
                    key={doc.run_id}
                    href={`/app/runs/${doc.run_id}`}
                    className="group flex items-center gap-3.5 px-4 py-3.5 transition-colors first:rounded-t-card last:rounded-b-card hover:bg-line/30 sm:px-5"
                  >
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-accent-soft">
                      <FileText className="size-4 text-accent" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">CV — {doc.target_role}</p>
                      <p className="mt-0.5 text-xs text-muted">{formatDate(doc.created_at)}</p>
                    </div>
                    <span className="hidden shrink-0 text-xs tabular-nums text-muted/60 sm:block">
                      #{String(generated.length - i).padStart(2, "0")}
                    </span>
                    <span className="text-xs font-medium text-muted opacity-0 transition-opacity group-hover:opacity-100">
                      Open
                    </span>
                  </Link>
                ))}
              </Card>
            </section>
          )}
        </div>
      )}
    </>
  );
}
