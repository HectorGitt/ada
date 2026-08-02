"use client";

import { Activity, Megaphone, ScrollText, Users, Wrench } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Logo, Spinner, ThemeToggle } from "@/components/ui";
import { api } from "@/lib/api";

const NAV = [
  { href: "/admin", label: "Overview", icon: Activity, exact: true },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/ops", label: "Operations", icon: Wrench },
  { href: "/admin/broadcast", label: "Broadcast", icon: Megaphone },
  { href: "/admin/audit", label: "Audit log", icon: ScrollText },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [state, setState] = useState<"checking" | "ok" | "denied">("checking");

  useEffect(() => {
    api.admin
      .me()
      .then(() => setState("ok"))
      .catch(() => setState("denied"));
  }, []);

  useEffect(() => {
    if (state === "denied") router.replace("/app");
  }, [state, router]);

  if (state !== "ok") {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <Spinner label={state === "denied" ? "Not authorized…" : "Checking access…"} />
      </div>
    );
  }

  return (
    <div className="flex min-h-dvh">
      <aside className="fixed inset-y-0 left-0 z-20 flex w-56 flex-col border-r border-line bg-surface max-md:hidden">
        <div className="flex items-center gap-2 px-5 pb-2 pt-5">
          <Logo />
          <span className="rounded-full bg-danger-soft px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-danger">
            Admin
          </span>
        </div>
        <nav className="flex-1 space-y-0.5 px-3 pt-4">
          {NAV.map(({ href, label, icon: Icon, exact }) => {
            const active = exact ? pathname === href : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors ${
                  active
                    ? "bg-accent-soft font-medium text-accent"
                    : "text-muted hover:bg-line/40 hover:text-ink"
                }`}
              >
                <Icon className="size-4" />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="flex items-center justify-between border-t border-line px-4 py-3">
          <Link href="/app" className="text-xs text-muted hover:text-ink">
            ← Back to app
          </Link>
          <ThemeToggle />
        </div>
      </aside>

      {/* Mobile top strip */}
      <header className="fixed inset-x-0 top-0 z-20 flex items-center gap-2 overflow-x-auto border-b border-line bg-surface/90 px-4 py-2.5 backdrop-blur md:hidden">
        {NAV.map(({ href, label, exact }) => {
          const active = exact ? pathname === href : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`shrink-0 rounded-full px-3 py-1.5 text-xs ${
                active ? "bg-accent-soft font-medium text-accent" : "text-muted"
              }`}
            >
              {label}
            </Link>
          );
        })}
      </header>

      <main className="flex-1 px-5 pb-16 pt-8 max-md:pt-16 md:ml-56 md:px-8">
        <div className="mx-auto max-w-5xl">{children}</div>
      </main>
    </div>
  );
}
