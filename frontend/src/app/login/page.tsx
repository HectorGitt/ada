"use client";

import { ArrowRight, Eye, EyeOff, MailCheck } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { ApiError, api } from "@/lib/api";
import { Button, Card, Input, Label, Logo, useUcheBrand } from "@/components/ui";

type Mode = "signin" | "signup" | "forgot";

const COPY: Record<Mode, { title: string; sub: string; cta: string }> = {
  signin: {
    title: "Welcome back",
    sub: "Sign in to pick up where Ada left off.",
    cta: "Sign in",
  },
  signup: {
    title: "Create your account",
    sub: "One account runs the whole loop — CV, matches, interview.",
    cta: "Create account",
  },
  forgot: {
    title: "Reset your password",
    sub: "Enter your email and we'll send a reset link.",
    cta: "Send reset link",
  },
};

/** Same flow, employer voice — shown on the uche.* subdomain. */
const UCHE_COPY: Record<Mode, { title: string; sub: string; cta: string }> = {
  signin: {
    title: "Welcome back",
    sub: "Sign in to your hiring console.",
    cta: "Sign in",
  },
  signup: {
    title: "Create your account",
    sub: "Post a role once — Uche screens, ranks, and preps the interviews.",
    cta: "Create account",
  },
  forgot: {
    title: "Reset your password",
    sub: "Enter your email and we'll send a reset link.",
    cta: "Send reset link",
  },
};

function LoginForm() {
  const params = useSearchParams();
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState(
    params.get("reset") === "done"
      ? ""
      : params.get("error") === "invalid_link"
        ? "That link is invalid or expired — request a fresh one."
        : "",
  );
  const [notice] = useState(
    params.get("reset") === "done" ? "Password updated. Sign in with your new password." : "",
  );

  const uche = useUcheBrand();
  const copy = (uche ? UCHE_COPY : COPY)[mode];

  const switchMode = (next: Mode) => {
    setMode(next);
    setError("");
    setSent(false);
    setPassword("");
  };

  // Honor ?next= for internal paths (e.g. /hire sends employers back after signin);
  // on the uche host the default destination is the hiring console itself.
  const rawNext = params.get("next") ?? "";
  const dest = rawNext.startsWith("/") && !rawNext.startsWith("//")
    ? rawNext
    : uche
      ? "/hire"
      : "/app";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "forgot") {
        await api.requestReset(email);
        setSent(true);
      } else if (mode === "signup") {
        await api.signup(email, password);
        router.push(dest);
      } else {
        await api.login(email, password);
        router.push(dest);
      }
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Something went wrong — try again in a moment.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="glow-field relative flex min-h-dvh flex-col items-center justify-center overflow-hidden px-4 py-10">
      <div className="dot-grid absolute inset-0 -z-10" aria-hidden />
      <Link href="/" className="mb-10">
        <Logo className="text-3xl" />
      </Link>

      <Card className="w-full max-w-sm p-8 shadow-lift">
        {mode === "forgot" && sent ? (
          <div className="flex flex-col items-center gap-3 text-center">
            <span className="flex size-12 items-center justify-center rounded-2xl bg-accent-soft">
              <MailCheck className="size-6 text-accent" />
            </span>
            <h1 className="display text-2xl">Check your inbox</h1>
            <p className="text-sm leading-relaxed text-muted">
              If <strong>{email}</strong> has an account, a reset link is on its way. It
              expires in 30 minutes.
            </p>
            <button
              onClick={() => switchMode("signin")}
              className="mt-1 text-xs text-muted underline underline-offset-2 transition-colors hover:text-ink"
            >
              Back to sign in
            </button>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <div>
              <h1 className="display text-2xl">{copy.title}</h1>
              <p className="mt-1 text-sm text-muted">{copy.sub}</p>
            </div>

            {notice && !error && (
              <p className="rounded-xl bg-success-soft px-3 py-2 text-sm text-success">
                {notice}
              </p>
            )}

            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                required
                autoFocus
                autoComplete="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            {mode !== "forgot" && (
              <div>
                <div className="mb-1.5 flex items-baseline justify-between">
                  <Label htmlFor="password">Password</Label>
                  {mode === "signin" && (
                    <button
                      type="button"
                      onClick={() => switchMode("forgot")}
                      className="text-xs text-muted underline-offset-2 transition-colors hover:text-ink hover:underline"
                    >
                      Forgot?
                    </button>
                  )}
                </div>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPw ? "text" : "password"}
                    required
                    minLength={mode === "signup" ? 8 : undefined}
                    autoComplete={mode === "signup" ? "new-password" : "current-password"}
                    placeholder={mode === "signup" ? "At least 8 characters" : "Your password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw((v) => !v)}
                    aria-label={showPw ? "Hide password" : "Show password"}
                    className="absolute inset-y-0 right-0 flex items-center px-3 text-muted transition-colors hover:text-ink"
                  >
                    {showPw ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                </div>
              </div>
            )}

            {error && <p className="text-sm text-danger">{error}</p>}

            <Button type="submit" loading={busy} className="group w-full">
              {copy.cta}
              <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
            </Button>
          </form>
        )}
      </Card>

      {/* Mode switch below the card — one line, never both password fields at once. */}
      {!(mode === "forgot" && sent) && (
        <p className="mt-6 text-xs text-muted">
          {mode === "signin" ? (
            <>
              New to {uche ? "Uche" : "Ada"}?{" "}
              <button
                onClick={() => switchMode("signup")}
                className="font-medium text-ink underline-offset-2 hover:underline"
              >
                Create an account
              </button>
            </>
          ) : mode === "signup" ? (
            <>
              Already have an account?{" "}
              <button
                onClick={() => switchMode("signin")}
                className="font-medium text-ink underline-offset-2 hover:underline"
              >
                Sign in
              </button>
            </>
          ) : (
            <button
              onClick={() => switchMode("signin")}
              className="font-medium text-ink underline-offset-2 hover:underline"
            >
              Back to sign in
            </button>
          )}
        </p>
      )}
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
