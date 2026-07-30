"use client";

import {
  CreditCard,
  FileText,
  Inbox,
  LayoutDashboard,
  LayoutList,
  MessageCircle,
  Mic,
  Plus,
  Send,
} from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";

import { NotificationBell } from "@/components/notification-bell";
import { Logo, Spinner, ThemeToggle } from "@/components/ui";
import { api, type MeOut } from "@/lib/api";

const AuthContext = createContext<MeOut | null>(null);
export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AppShell");
  return ctx;
};

type NavItem = {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  exact?: boolean;
};

const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: "Workspace",
    items: [
      { href: "/app", label: "Home", icon: LayoutDashboard, exact: true },
      { href: "/app/new", label: "New run", icon: Plus },
      { href: "/app/runs", label: "My runs", icon: LayoutList },
      { href: "/app/documents", label: "Documents", icon: FileText },
      { href: "/app/applications", label: "Applications", icon: Send },
      { href: "/app/intros", label: "Intros", icon: Inbox },
    ],
  },
  {
    label: "Coach",
    items: [
      { href: "/app/coach", label: "Ask Ada", icon: MessageCircle },
      { href: "/app/voice", label: "Voice intake", icon: Mic },
    ],
  },
  {
    label: "Account",
    items: [{ href: "/app/billing", label: "Plans & billing", icon: CreditCard }],
  },
];

/* Crafted tab icons from the mobile design canvas — thinner strokes and
 * friendlier geometry than the stock set. */
const TabIcon = {
  home: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5 9.5V21h5v-6h4v6h5V9.5" />
    </svg>
  ),
  runs: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
      <path d="M4 6h16M4 12h16M4 18h10" />
    </svg>
  ),
  ask: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12a8 8 0 1 1-3.1-6.3L21 5l-.6 3.2A8 8 0 0 1 21 12z" />
    </svg>
  ),
  you: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 20c1.4-3.2 4-5 7-5s5.6 1.8 7 5" />
    </svg>
  ),
} as const;

const isActive = (pathname: string, item: { href: string; exact?: boolean }) =>
  item.exact ? pathname === item.href : pathname.startsWith(item.href);

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<MeOut | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    api
      .me()
      .then(setUser)
      .catch(() => router.replace("/login"))
      .finally(() => setChecking(false));
  }, [router]);

  if (checking || !user) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <Spinner label="Opening Ada..." />
      </div>
    );
  }

  return (
    <AuthContext.Provider value={user}>
      <div className="flex min-h-dvh">
        <aside className="fixed inset-y-0 left-0 z-20 flex w-60 flex-col border-r border-line bg-surface max-lg:hidden">
          <div className="px-5 pb-2 pt-5">
            <Link href="/">
              <Logo />
            </Link>
          </div>
          <nav className="flex-1 space-y-6 px-3 pt-4">
            {NAV_GROUPS.map((group) => (
              <div key={group.label}>
                <p className="eyebrow mb-2 px-3 !text-[10px]">{group.label}</p>
                <div className="space-y-0.5">
                  {group.items.map((item) => {
                    const { href, label, icon: Icon } = item;
                    const active = isActive(pathname, item);
                    return (
                      <Link
                        key={href}
                        href={href}
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
                        <Icon
                          className={`size-4 transition-transform ${active ? "" : "group-hover:scale-110"}`}
                        />
                        {label}
                      </Link>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>
          <div className="border-t border-line px-3 py-3">
            <div className="flex items-center gap-2.5 rounded-xl px-2 py-1.5">
              <Link
                href="/app/profile"
                className="flex min-w-0 flex-1 items-center gap-2.5"
                title={user.email}
              >
                <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold uppercase text-accent">
                  {user.email[0]}
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-xs font-medium">{user.email}</span>
                  <span className="block text-[10px] text-muted">View profile</span>
                </span>
              </Link>
              <NotificationBell />
              <ThemeToggle />
            </div>
          </div>
        </aside>

        {/* Mobile: slim top bar + floating liquid-glass tab bar (from the
            mobile design canvas: blurred pill, raised accent FAB for New run) */}
        <header className="fixed inset-x-0 top-0 z-20 flex items-center justify-between border-b border-line bg-surface/90 px-4 py-3 backdrop-blur lg:hidden">
          <Link href="/">
            <Logo />
          </Link>
          <div className="flex items-center gap-1.5">
            <NotificationBell />
            <ThemeToggle />
            <Link
              href="/app/profile"
              aria-label="Profile"
              className="flex size-8 items-center justify-center rounded-full border border-accent/15 bg-accent-soft text-xs font-semibold uppercase text-accent"
            >
              {user.email[0]}
            </Link>
          </div>
        </header>
        <nav
          className="fixed inset-x-4 bottom-0 z-20 lg:hidden"
          style={{ marginBottom: "calc(env(safe-area-inset-bottom) + 12px)" }}
          aria-label="Primary"
        >
          <div className="mx-auto flex max-w-md items-center justify-around rounded-[32px] border border-line/90 bg-surface/80 px-2.5 py-2 shadow-lift backdrop-blur-xl">
            {(
              [
                { href: "/app", label: "Home", icon: TabIcon.home, exact: true },
                { href: "/app/runs", label: "Runs", icon: TabIcon.runs },
              ] as const
            ).map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-label={item.label}
                className={`flex flex-col items-center gap-0.5 px-3 py-1 text-[9px] ${
                  isActive(pathname, item) ? "font-semibold text-accent" : "text-muted"
                }`}
              >
                {item.icon}
                {item.label}
              </Link>
            ))}
            <Link
              href="/app/new"
              aria-label="New run"
              className="-mt-7 flex size-12 items-center justify-center rounded-full bg-accent text-accent-ink shadow-[0_1px_2px_rgba(23,21,15,0.16),0_6px_16px_rgba(67,56,202,0.35)] transition-transform active:scale-95"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M12 5v14M5 12h14" />
              </svg>
            </Link>
            {(
              [
                { href: "/app/coach", label: "Ask Ada", icon: TabIcon.ask },
                { href: "/app/profile", label: "You", icon: TabIcon.you },
              ] as const
            ).map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-label={item.label}
                className={`flex flex-col items-center gap-0.5 px-3 py-1 text-[9px] ${
                  isActive(pathname, item) ? "font-semibold text-accent" : "text-muted"
                }`}
              >
                {item.icon}
                {item.label}
              </Link>
            ))}
          </div>
        </nav>

        <main className="flex-1 px-6 pb-28 pt-8 max-lg:pt-20 lg:ml-60 lg:px-10 lg:pb-16">
          {/* Keyed by route so every page glides in */}
          <motion.div
            key={pathname}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: [0.21, 0.6, 0.35, 1] }}
            className="mx-auto max-w-3xl"
          >
            {children}
          </motion.div>
        </main>
      </div>
    </AuthContext.Provider>
  );
}
