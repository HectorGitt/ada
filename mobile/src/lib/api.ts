/** Typed client for the Ada backend — the same endpoints the web app uses.
 *  Point EXPO_PUBLIC_API_URL at the FastAPI origin; the session cookie
 *  persists through React Native's native networking stack. */

export const API_BASE =
  process.env.EXPO_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8080";

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

export interface Profile {
  profile_text: string;
  linkedin_url: string | null;
  updated_at: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export type OutcomeStage = "applied" | "interviewing" | "offer" | "hired" | "rejected";

export interface Outcome {
  id: string;
  company: string;
  role_title: string;
  stage: OutcomeStage;
  source: string;
  updated_at: string;
}

export interface Pipeline {
  outcomes: Outcome[];
  funnel: Record<string, number>;
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
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
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
  me: () => request<{ email: string }>("/api/auth/me"),
  logout: () => request<{ status: string }>("/api/auth/logout", { method: "POST" }),

  // runs
  createRun: (body: {
    email: string;
    target_role: string;
    cv_text: string;
    provider: "paystack" | "stripe";
    transcript?: string | null;
  }) =>
    request<CreateRunOut>("/api/runs", { method: "POST", body: JSON.stringify(body) }),
  listRuns: () => request<RunSummary[]>("/api/runs"),
  getRun: (id: string) => request<RunResult>(`/api/runs/${id}`),
  scoreInterview: (id: string, answers: string[]) =>
    request<Scorecard>(`/api/runs/${id}/interview`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    }),

  // profile
  getProfile: () => request<Profile | null>("/api/profile"),
  putProfile: (body: { profile_text: string; linkedin_url?: string | null }) =>
    request<Profile>("/api/profile", { method: "PUT", body: JSON.stringify(body) }),

  // outcomes (hiring funnel)
  getPipeline: () => request<Pipeline>("/api/outcomes"),
  addOutcome: (company: string, role_title: string, stage: OutcomeStage) =>
    request<Outcome>("/api/outcomes", {
      method: "POST",
      body: JSON.stringify({ company, role_title, stage }),
    }),
  advanceOutcome: (id: string, stage: OutcomeStage) =>
    request<Outcome>(`/api/outcomes/${id}`, {
      method: "PUT",
      body: JSON.stringify({ stage }),
    }),
};

/** Stream a chat completion. React Native's fetch has no ReadableStream, so
 *  this parses the SSE body incrementally off XMLHttpRequest progress events —
 *  which also works on web. */
export function streamChat(
  messages: ChatMessage[],
  onDelta: (text: string) => void,
): { done: Promise<void>; abort: () => void } {
  const xhr = new XMLHttpRequest();
  let seen = 0;
  const done = new Promise<void>((resolve, reject) => {
    xhr.open("POST", `${API_BASE}/api/chat`);
    xhr.withCredentials = true;
    xhr.setRequestHeader("Content-Type", "application/json");
    const pump = () => {
      const text = xhr.responseText ?? "";
      // Only complete events (terminated by a blank line) are consumed.
      const end = text.lastIndexOf("\n\n");
      if (end <= seen) return;
      const chunk = text.slice(seen, end);
      seen = end + 2;
      for (const event of chunk.split("\n\n")) {
        const data = event.replace(/^data: /, "").trim();
        if (!data || data === "[DONE]") continue;
        try {
          const parsed = JSON.parse(data) as { delta?: string; error?: string };
          if (parsed.error) throw new Error(parsed.error);
          if (parsed.delta) onDelta(parsed.delta);
        } catch (err) {
          reject(err instanceof Error ? err : new Error("stream parse failed"));
          xhr.abort();
          return;
        }
      }
    };
    xhr.onprogress = pump;
    xhr.onload = () => {
      pump();
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else reject(new ApiError(xhr.status, "chat failed"));
    };
    xhr.onerror = () => reject(new ApiError(0, "network error"));
    xhr.onabort = () => resolve();
    xhr.send(JSON.stringify({ messages }));
  });
  return { done, abort: () => xhr.abort() };
}

/** WebSocket base for the voice intake. */
export function voiceWsUrl(): string {
  return `${API_BASE.replace(/^http/, "ws")}/api/voice`;
}
