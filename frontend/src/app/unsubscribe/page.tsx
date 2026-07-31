"use client";

import { Check, Loader2 } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Button, Logo } from "@/components/ui";
import { api } from "@/lib/api";

function Unsubscribe() {
  const token = useSearchParams().get("token") ?? "";
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!token) {
      setDone(true);
      return;
    }
    api.unsubscribe(token).finally(() => setDone(true));
  }, [token]);

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center px-5 text-center">
      <Link href="/" className="mb-8">
        <Logo />
      </Link>
      {!done ? (
        <Loader2 className="size-6 animate-spin text-muted" />
      ) : (
        <>
          <span className="mb-4 inline-flex size-12 items-center justify-center rounded-full bg-success-soft text-success">
            <Check className="size-6" />
          </span>
          <h1 className="display text-3xl">You&apos;re unsubscribed.</h1>
          <p className="mt-3 max-w-sm text-muted">
            You won&apos;t get email or WhatsApp notifications from Ada. You can turn any of
            them back on anytime under Notifications in your profile.
          </p>
          <Link href="/app/profile" className="mt-6">
            <Button variant="secondary">Manage preferences</Button>
          </Link>
        </>
      )}
    </main>
  );
}

export default function UnsubscribePage() {
  return (
    <Suspense fallback={null}>
      <Unsubscribe />
    </Suspense>
  );
}
