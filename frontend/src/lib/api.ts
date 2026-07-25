/** Typed client for the Ada backend. Every server call in the app goes through here. */

export type RunStatus = "pending_payment" | "paid" | "running" | "complete" | "failed";

export interface CreateRunOut {
  run_id: string;
  reference: string;
  provider: "paystack" | "stripe";
  public_key: string | null;
  amount: number | null;
  currency: string | null;
  checkout_url: string | null;
}

export interface Match {
  title: string;
  company: string;
  location: string;
  match: number;
  reason: string;
}

export interface AnswerScore {
  question: string;
  answer: string;
  score: number;
  feedback: string;
}

export interface Scorecard {
  scores: AnswerScore[];
  overall_score: number;
  summary: string;
}

export interface RunResult {
  status: RunStatus;
  /** Graph node currently executing while RUNNING; null otherwise. */
  stage?: "intake" | "cv_rewrite" | "job_match" | "interview_prep" | null;
  target_role: string;
  rewritten_cv: string | null;
  matches: Match[] | null;
  questions: string[] | null;
  interview: Scorecard | null;
}

export interface RunSummary {
  run_id: string;
  target_role: string;
  status: RunStatus;
  created_at: string;
  has_interview: boolean;
}

/** How each run status reads in the UI — label plus the badge tone it maps to.
 *  Single source of truth so the dashboard and runs list can't drift apart. */
export const RUN_STATUS: Record<
  RunStatus,
  { label: string; tone: "neutral" | "accent" | "success" | "warn" | "danger"; pulse?: boolean }
> = {
  pending_payment: { label: "Awaiting payment", tone: "warn" },
  paid: { label: "Queued", tone: "accent" },
  running: { label: "Running", tone: "accent", pulse: true },
  complete: { label: "Complete", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
};

export interface Profile {
  profile_text: string;
  linkedin_url: string | null;
  updated_at: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface JobPeek {
  title: string;
  company: string;
  location: string;
}

export interface JobsPreview {
  count: number;
  samples: JobPeek[];
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  // auth
  signup: (email: string, password: string) =>
    request<{ email: string }>("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  login: (email: string, password: string) =>
    request<{ email: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  requestReset: (email: string) =>
    request<{ status: string }>("/api/auth/request-reset", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  resetPassword: (token: string, password: string) =>
    request<{ status: string }>("/api/auth/reset", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    }),
  me: () => request<{ email: string }>("/api/auth/me"),
  logout: () => request<{ status: string }>("/api/auth/logout", { method: "POST" }),

  // runs
  createRun: (body: {
    email: string;
    target_role: string;
    cv_text: string;
    provider: "paystack" | "stripe";
    transcript?: string | null;
  }) => request<CreateRunOut>("/api/runs", { method: "POST", body: JSON.stringify(body) }),
  listRuns: () => request<RunSummary[]>("/api/runs"),
  getRun: (id: string) => request<RunResult>(`/api/runs/${id}`),
  /** Cheap pre-payment teaser: count + a few raw titles, no scores/reasons. */
  jobsPreview: (role: string) =>
    request<JobsPreview>(`/api/jobs/preview?role=${encodeURIComponent(role)}`),
  scoreInterview: (id: string, answers: string[]) =>
    request<Scorecard>(`/api/runs/${id}/interview`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    }),

  // documents
  uploadCv: async (file: File) => {
    const body = new FormData();
    body.append("file", file);
    const res = await fetch("/api/documents/cv", {
      method: "POST",
      credentials: "same-origin",
      body,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        detail = ((await res.json()) as { detail?: string }).detail ?? detail;
      } catch {
        /* non-JSON error body */
      }
      throw new ApiError(res.status, detail);
    }
    return res.json() as Promise<{ cv_text: string; gcs_uri: string | null; filename: string }>;
  },

  // profile
  getProfile: () => request<Profile | null>("/api/profile"),
  putProfile: (body: { profile_text: string; linkedin_url?: string | null }) =>
    request<Profile>("/api/profile", { method: "PUT", body: JSON.stringify(body) }),
};

/** Stream a chat completion; calls onDelta per text chunk. Returns the full reply. */
export async function streamChat(
  messages: ChatMessage[],
  onDelta: (text: string) => void,
  signal?: AbortSignal,
): Promise<string> {
  const res = await fetch("/api/chat", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
    signal,
  });
  if (!res.ok || !res.body) throw new ApiError(res.status, "chat failed");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let full = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const event of events) {
      const data = event.replace(/^data: /, "").trim();
      if (!data || data === "[DONE]") continue;
      const parsed = JSON.parse(data) as { delta?: string; error?: string };
      if (parsed.error) throw new Error(parsed.error);
      if (parsed.delta) {
        full += parsed.delta;
        onDelta(parsed.delta);
      }
    }
  }
  return full;
}

/** Backend WebSocket base for the voice intake (rewrites don't proxy upgrades). */
export function voiceWsUrl(): string {
  const base =
    process.env.NEXT_PUBLIC_WS_URL ??
    (typeof window !== "undefined"
      ? `${window.location.protocol === "https:" ? "wss" : "ws"}://localhost:8080`
      : "ws://localhost:8080");
  return `${base}/api/voice`;
}
