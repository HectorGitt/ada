"use client";

import { Loader2, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const buttonStyles: Record<ButtonVariant, string> = {
  primary:
    "bg-accent text-accent-ink shadow-btn hover:opacity-[.92] hover:-translate-y-px active:translate-y-0",
  secondary:
    "bg-surface border border-line text-ink shadow-card hover:border-ink/30 hover:-translate-y-px active:translate-y-0",
  ghost: "text-muted hover:text-ink hover:bg-line/40",
  danger: "bg-danger text-white hover:opacity-90",
};

export function Button({
  variant = "primary",
  loading = false,
  className = "",
  children,
  disabled,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  loading?: boolean;
}) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium transition-all duration-200 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 ${buttonStyles[variant]} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Loader2 className="size-4 animate-spin" />}
      {children}
    </button>
  );
}

export function Card({
  className = "",
  hover = false,
  children,
}: {
  className?: string;
  hover?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`rounded-card border border-line bg-surface shadow-card ${
        hover
          ? "transition-all duration-200 hover:-translate-y-0.5 hover:border-ink/25 hover:shadow-lift active:translate-y-0 active:scale-[0.995]"
          : ""
      } ${className}`}
    >
      {children}
    </div>
  );
}

export function Label({
  htmlFor,
  children,
}: {
  htmlFor?: string;
  children: React.ReactNode;
}) {
  return (
    <label htmlFor={htmlFor} className="mb-1.5 block text-[13px] font-medium text-ink">
      {children}
    </label>
  );
}

const fieldClass =
  "w-full rounded-xl border border-line bg-surface px-3.5 py-2.5 text-sm text-ink placeholder:text-muted/70 outline-none transition-all focus:border-accent focus:ring-2 focus:ring-accent/20";

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${fieldClass} ${props.className ?? ""}`} />;
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`${fieldClass} min-h-32 resize-y quiet-scroll ${props.className ?? ""}`}
    />
  );
}

/** True on the employer subdomain (uche.*) — the same app wearing Uche's brand. */
export function useUcheBrand(): boolean {
  const [uche, setUche] = useState(false);
  useEffect(() => {
    if (window.location.hostname.startsWith("uche.")) setUche(true);
  }, []);
  return uche;
}

export function Logo({ className = "" }: { className?: string }) {
  const uche = useUcheBrand();
  return (
    <span className={`display select-none text-[1.35rem] leading-none text-ink ${className}`}>
      {uche ? "Uche" : "Ada"}<span className="text-accent">.</span>
    </span>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-muted">
      <Loader2 className="size-4 animate-spin" />
      {label}
    </div>
  );
}

/** Standard page heading for app screens: serif title + quiet subtitle. */
export function PageHeader({
  title,
  subtitle,
  action,
  className = "",
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`mb-8 flex flex-wrap items-end justify-between gap-4 ${className}`}>
      <div className="min-w-0">
        <h1 className="display text-3xl sm:text-[2.15rem]">{title}</h1>
        {subtitle && (
          <p className="mt-2 max-w-lg text-sm leading-relaxed text-muted">{subtitle}</p>
        )}
      </div>
      {action}
    </div>
  );
}

/** Small-caps section label with a short rule, used to open landing sections. */
export function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <p className="eyebrow mb-4 flex items-center gap-3">
      <span className="h-px w-8 bg-accent" aria-hidden />
      {children}
    </p>
  );
}

/** Uppercase heading with a short accent rule — opens sections inside app screens
 *  (run detail, dashboard) where a full serif PageHeader would be too loud. */
export function SectionTitle({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <h2
      className={`flex items-center gap-3 text-sm font-semibold uppercase tracking-wide text-muted ${className}`}
    >
      <span className="h-px w-6 bg-accent" aria-hidden />
      {children}
    </h2>
  );
}

type BadgeTone = "neutral" | "accent" | "success" | "warn" | "danger";

const badgeStyles: Record<BadgeTone, string> = {
  neutral: "bg-surface-2 text-muted",
  accent: "bg-accent-soft text-accent",
  success: "bg-success-soft text-success",
  warn: "bg-warn-soft text-warn",
  danger: "bg-danger-soft text-danger",
};

/** Status pill with a leading dot — run states, live indicators. */
export function StatusBadge({
  tone = "neutral",
  pulse = false,
  children,
}: {
  tone?: BadgeTone;
  pulse?: boolean;
  children: React.ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium ${badgeStyles[tone]}`}
    >
      <span
        className={`size-1.5 shrink-0 rounded-full bg-current ${pulse ? "pulse-soft" : ""}`}
      />
      {children}
    </span>
  );
}

/** Shimmering placeholder block for loading states. */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden />;
}

/** Radial gauge: an accent ring that draws itself in on mount. Children render
 *  centered inside — pair a serif number with a quiet unit. */
export function ScoreRing({
  value,
  max = 100,
  size = 96,
  stroke = 7,
  className = "",
  children,
}: {
  value: number;
  max?: number;
  size?: number;
  stroke?: number;
  className?: string;
  children?: React.ReactNode;
}) {
  const [drawn, setDrawn] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setDrawn(true));
    return () => cancelAnimationFrame(id);
  }, []);
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, value / max));
  return (
    <div
      className={`relative inline-flex items-center justify-center ${className}`}
      style={{ width: size, height: size }}
      role="img"
      aria-label={`${value} out of ${max}`}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--line)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--accent)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - (drawn ? pct : 0))}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: "stroke-dashoffset 1.1s cubic-bezier(0.21, 0.6, 0.35, 1)" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center leading-none">
        {children}
      </div>
    </div>
  );
}

/** Horizontal 0-100 meter used for match percentages and interview scores. */
export function ScoreBar({ value, max = 100 }: { value: number; max?: number }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-line">
      <div
        className="h-full rounded-full bg-gradient-to-r from-accent/70 to-accent transition-[width] duration-700 ease-out"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);
  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.theme = next ? "dark" : "light";
  };
  return (
    <button
      onClick={toggle}
      aria-label="Toggle theme"
      className="rounded-full p-2 text-muted transition-colors hover:bg-line/40 hover:text-ink"
    >
      {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </button>
  );
}

export function EmptyState({
  icon,
  title,
  body,
  action,
}: {
  icon?: React.ReactNode;
  title: string;
  body: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-card border border-dashed border-line bg-surface/50 px-8 py-16 text-center">
      {icon && (
        <div className="mb-1 flex size-12 items-center justify-center rounded-2xl bg-accent-soft text-accent">
          {icon}
        </div>
      )}
      <p className="display text-2xl">{title}</p>
      <p className="max-w-sm text-sm leading-relaxed text-muted">{body}</p>
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
