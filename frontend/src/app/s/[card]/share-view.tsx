"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { Button, Card, Logo, ScoreRing, ThemeToggle } from "@/components/ui";
import { verdict } from "@/lib/share";

export function ShareView({ score, role }: { score: number; role?: string }) {
  return (
    <div className="min-h-dvh bg-bg">
      <header className="mx-auto flex max-w-3xl items-center justify-between px-5 py-4">
        <Link href="/" aria-label="Ada home">
          <Logo />
        </Link>
        <ThemeToggle />
      </header>

      <main className="mx-auto max-w-2xl px-5 pb-24 pt-10 text-center">
        <p className="eyebrow mb-3">CV readiness</p>
        <Card className="flex flex-col items-center gap-5 p-8 sm:flex-row sm:text-left">
          <ScoreRing value={score} size={112} stroke={9} />
          <div>
            <p className="display text-3xl">{verdict(score)}</p>
            {role && <p className="mt-1 text-muted">for {role}</p>}
            <p className="mt-2 text-sm text-muted">
              Scored by Ada — the career agent that rewrites your CV, finds your best-fit
              roles, and preps your interview.
            </p>
          </div>
        </Card>

        <div className="mt-10">
          <h1 className="display text-3xl sm:text-4xl">How ready is your CV?</h1>
          <p className="mx-auto mt-3 max-w-md text-muted">
            Paste yours in and Ada scores it free — with the three highest-impact fixes.
            No signup.
          </p>
          <Link href="/assess">
            <Button className="group mt-5 !px-7 !py-3">
              Check my CV free
              <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
            </Button>
          </Link>
        </div>
      </main>
    </div>
  );
}
