"use client";

import { Briefcase, Globe, MapPin, Users } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Card, Logo, Skeleton, ThemeToggle } from "@/components/ui";
import { ApiError, api, type PublicCompany } from "@/lib/api";

export default function CompanyPublicPage() {
  const { id } = useParams<{ id: string }>();
  const [c, setC] = useState<PublicCompany | null | "notfound">(null);

  useEffect(() => {
    api
      .publicCompany(id)
      .then(setC)
      .catch((e) => setC(e instanceof ApiError && e.status === 404 ? "notfound" : null));
  }, [id]);

  return (
    <div className="min-h-dvh bg-bg">
      <header className="mx-auto flex max-w-3xl items-center justify-between px-5 py-4">
        <Link href="/" aria-label="Ada home">
          <Logo />
        </Link>
        <ThemeToggle />
      </header>

      <main className="mx-auto max-w-3xl px-5 pb-24 pt-6">
        {c === null ? (
          <Skeleton className="h-48 w-full" />
        ) : c === "notfound" ? (
          <p className="text-sm text-muted">This company page isn&apos;t available.</p>
        ) : (
          <>
            <div className="flex items-center gap-4">
              {c.logo_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={c.logo_url} alt="" className="size-16 rounded-2xl border border-line object-cover" />
              ) : (
                <div className="flex size-16 items-center justify-center rounded-2xl bg-accent-soft text-2xl font-semibold text-accent">
                  {c.name[0]}
                </div>
              )}
              <div>
                <h1 className="display text-3xl">{c.name}</h1>
                <p className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-sm text-muted">
                  {c.industry && <span>{c.industry}</span>}
                  {c.size && (
                    <span className="flex items-center gap-1">
                      <Users className="size-3.5" /> {c.size}
                    </span>
                  )}
                  {c.location && (
                    <span className="flex items-center gap-1">
                      <MapPin className="size-3.5" /> {c.location}
                    </span>
                  )}
                  {c.website && (
                    <a href={c.website} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-accent hover:underline">
                      <Globe className="size-3.5" /> Website
                    </a>
                  )}
                </p>
              </div>
            </div>

            {c.about && <p className="mt-6 whitespace-pre-line leading-relaxed text-ink/90">{c.about}</p>}

            {c.roles.length > 0 && (
              <div className="mt-8">
                <p className="eyebrow mb-3">Open roles</p>
                <div className="space-y-2">
                  {c.roles.map((r) => (
                    <Card key={r.id} className="flex items-center gap-3 px-4 py-3">
                      <Briefcase className="size-4 shrink-0 text-muted" />
                      <div>
                        <p className="text-sm font-medium">{r.title}</p>
                        <p className="text-xs text-muted">{r.remote ? "Remote" : r.location}</p>
                      </div>
                    </Card>
                  ))}
                </div>
              </div>
            )}

            <Card className="mt-10 border-accent/30 bg-accent-soft/40 p-5 text-center">
              <p className="text-sm text-muted">
                Reached out to you through <span className="font-medium text-ink">Ada</span> — the
                career agent. Get your own CV rewritten and matched, free to check.
              </p>
              <Link href="/assess" className="mt-2 inline-block text-sm font-medium text-accent hover:underline">
                Check your CV free →
              </Link>
            </Card>
          </>
        )}
      </main>
    </div>
  );
}
