"use client";

import { ArrowRight, Briefcase, CreditCard, Send, UserRound } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";

import { NotificationBell } from "@/components/notification-bell";
import { Button, Input, Label, Spinner, ThemeToggle } from "@/components/ui";
import { ApiError, api, type MeOut } from "@/lib/api";

/** Employer app shell — Ada's AppShell, in Uche's voice. Auth-gates the console,
 *  turns a candidate into an employer inline, then frames /hire in a sidebar. */

const EmployerContext = createContext<MeOut | null>(null);
export const useEmployer = () => {
  const ctx = useContext(EmployerContext);
  if (!ctx) throw new Error("useEmployer outside EmployerShell");
  return ctx;
};

const NAV = [
  { href: "/hire", label: "Roles", icon: Briefcase, exact: true },
  { href: "/hire/intros", label: "Intros", icon: Send },
  { href: "/hire/billing", label: "Billing", icon: CreditCard },
];

function UcheMark() {
  return (
    <span className="display select-none text-[1.35rem] leading-none text-ink">
      Uche<span className="text-accent">.</span>
    </span>
  );
}

function isActive(pathname: string, item: { href: string; exact?: boolean }): boolean {
  return item.exact ? pathname === item.href : pathname.startsWith(item.href);
}

export function EmployerShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [me, setMe] = useState<MeOut | null>(null);
  const [state, setState] = useState<"loading" | "anon" | "candidate" | "employer">("loading");

  useEffect(() => {
    api
      .me()
      .then((m) => {
        setMe(m);
        setState(m.account_type === "employer" ? "employer" : "candidate");
      })
      .catch(() => setState("anon"));
  }, []);

  useEffect(() => {
    if (state === "anon") router.replace("/login?next=/hire");
  }, [state, router]);

  if (state === "loading" || state === "anon") {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <Spinner label="Opening Uche..." />
      </div>
    );
  }

  if (state === "candidate" && me) {
    return <BecomeEmployer email={me.email} onDone={() => location.reload()} />;
  }

  return (
    <EmployerContext.Provider value={me}>
      <div className="flex min-h-dvh">
        <aside className="fixed inset-y-0 left-0 z-20 flex w-60 flex-col border-r border-line bg-surface max-lg:hidden">
          <div className="px-5 pb-2 pt-5">
            <Link href="/hire" aria-label="Uche home">
              <UcheMark />
            </Link>
          </div>
          <nav className="flex-1 space-y-0.5 px-3 pt-5">
            <p className="eyebrow mb-2 px-3 !text-[10px]">Hiring</p>
            {NAV.map((item) => {
              const active = isActive(pathname, item);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors ${
                    active
                      ? "bg-accent-soft font-medium text-accent"
                      : "text-muted hover:bg-line/40 hover:text-ink"
                  }`}
                >
                  {active && (
                    <span
                      className="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-accent"
                      aria-hidden
                    />
                  )}
                  <Icon className={`size-4 transition-transform ${active ? "" : "group-hover:scale-110"}`} />
                  {item.label}
                </Link>
              );
            })}
            <a
              href="https://ada.recrulus.com"
              className="mt-1 flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-muted transition-colors hover:bg-line/40 hover:text-ink"
            >
              <UserRound className="size-4" />
              Candidate view
            </a>
          </nav>
          <div className="border-t border-line px-3 py-3">
            <div className="flex items-center gap-2.5 rounded-xl px-2 py-1.5">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold uppercase text-accent">
                {(me?.company ?? me?.email ?? "U")[0]}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-xs font-medium">{me?.company ?? me?.email}</span>
                <span className="block text-[10px] text-muted">Hiring workspace</span>
              </span>
              <NotificationBell />
              <ThemeToggle />
            </div>
          </div>
        </aside>

        <header className="fixed inset-x-0 top-0 z-20 flex items-center justify-between border-b border-line bg-surface/90 px-4 py-3 backdrop-blur lg:hidden">
          <Link href="/hire" aria-label="Uche home">
            <UcheMark />
          </Link>
          <ThemeToggle />
        </header>
        <nav
          className="fixed inset-x-4 bottom-0 z-20 lg:hidden"
          style={{ marginBottom: "calc(env(safe-area-inset-bottom) + 12px)" }}
          aria-label="Primary"
        >
          <div className="mx-auto flex max-w-md items-center justify-around rounded-[32px] border border-line/90 bg-surface/80 px-4 py-2.5 shadow-lift backdrop-blur-xl">
            {NAV.map((item) => {
              const active = isActive(pathname, item);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-label={item.label}
                  className={`flex flex-col items-center gap-1 px-4 py-1 text-[10px] ${
                    active ? "font-semibold text-accent" : "text-muted"
                  }`}
                >
                  <Icon className="size-5" />
                  {item.label}
                </Link>
              );
            })}
          </div>
        </nav>

        <main className="flex-1 px-6 pb-28 pt-8 max-lg:pt-20 lg:ml-60 lg:px-10 lg:pb-16">
          <motion.div
            key={pathname}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: [0.21, 0.6, 0.35, 1] }}
            className="mx-auto max-w-4xl"
          >
            {children}
          </motion.div>
        </main>
      </div>
    </EmployerContext.Provider>
  );
}

function BecomeEmployer({ email, onDone }: { email: string; onDone: () => void }) {
  const [company, setCompany] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.setAccount("employer", company.trim());
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't switch to hiring mode.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto flex min-h-dvh max-w-lg flex-col justify-center px-5">
      <div className="mb-8 text-center">
        <span className="mb-4 inline-flex size-14 items-center justify-center rounded-2xl bg-ink text-bg">
          <Briefcase className="size-6" />
        </span>
        <h1 className="display text-4xl">Hire with Uche.</h1>
        <p className="mx-auto mt-3 max-w-sm text-muted">
          Uche reads your role and brings a shortlist of vetted candidates — each already
          assessed by Ada, each with the reason they fit. No job boards, no noise.
        </p>
      </div>
      <div className="rounded-card border border-line bg-surface p-7 shadow-card">
        <form onSubmit={submit} className="space-y-4">
          <div>
            <Label htmlFor="company">Company name</Label>
            <Input id="company" required autoFocus placeholder="Acme Foods" value={company} onChange={(e) => setCompany(e.target.value)} />
          </div>
          <p className="text-xs text-muted">
            Signed in as {email}. Switching to hiring mode keeps your candidate data intact.
          </p>
          {error && <p className="text-sm text-danger">{error}</p>}
          <Button type="submit" loading={busy} className="w-full !py-3">
            Enter hiring mode
            <ArrowRight className="size-4" />
          </Button>
        </form>
      </div>
    </div>
  );
}
