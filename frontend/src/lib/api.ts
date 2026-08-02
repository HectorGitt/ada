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
  entitled: boolean;
}

export interface PlanPrice {
  ngn_kobo: number;
  usd_cents: number;
}

export interface Plan {
  tier: string; // "pro" | "premium" (candidate) or "growth" | "scale" (employer)
  name: string;
  tagline: string;
  features: string[];
  monthly: PlanPrice;
  annual: PlanPrice;
}

export interface EmployerPlan {
  tier: "pilot" | "growth" | "scale";
  max_roles: number | null;
  max_intros: number | null;
  placement_support: boolean;
  roles_used: number;
  intros_used: number;
}

export interface SubscriptionState {
  tier: "free" | "pro" | "premium";
  status: string;
  cadence: "monthly" | "annual";
  current_period_end: string | null;
  can_apply: boolean;
  can_voice: boolean;
}

export interface Match {
  job_id?: number | null;
  title: string;
  company: string;
  location: string;
  url?: string | null;
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
  full_name: string | null;
  phone: string | null;
  compensation: string | null;
  work_pref: string | null;
  updated_at: string;
}

export interface MeOut {
  email: string;
  account_type: "candidate" | "employer";
  company: string | null;
}

export interface CandidateInsight {
  headline: string;
  seniority: string;
  years_experience: number;
  location: string;
  experience: string[];
  education: string;
  top_skills: string[];
  strengths: string[];
  growth_areas: string[];
  compensation: string;
  work_pref: string;
  market_fit: string;
  readiness_score: number;
  summary: string;
}

export interface InsightsOut {
  insights: CandidateInsight | null;
  ready: boolean;
  reason?: string;
  discoverable?: boolean;
}

export interface EmployerJob {
  id: number;
  title: string;
  company: string;
  location: string;
  remote: boolean;
  description: string;
}

export interface CandidateCard {
  user_id: string;
  headline: string | null;
  location: string | null;
  seniority: string | null;
  years_experience: number | null;
  top_skills: string[];
  compensation: string | null;
  work_pref: string | null;
  verified: Credential | null;
  match: number;
  verdict: string;
  rationale: string;
  intro_requested?: boolean;
}

export interface Shortlist {
  summary: string;
  candidates: CandidateCard[];
  unavailable?: boolean;
}

export interface EmployerIntro {
  id: string;
  job_id: number;
  candidate_id: string;
  candidate_headline: string | null;
  status: string;
  message: string | null;
  created_at: string;
  contact: { email: string | null; phone: string | null } | null;
}

export interface CandidateIntro {
  id: string;
  status: "requested" | "accepted" | "declined";
  message: string | null;
  created_at: string;
  role_title: string;
  company: string;
  location: string;
  remote: boolean;
}

// ── employer console ──
export interface CompanyProfile {
  name: string;
  website: string | null;
  industry: string | null;
  size: string | null;
  location: string | null;
  about: string | null;
  logo_url: string | null;
  contact_name: string | null;
  contact_title: string | null;
}

export interface EmployerOverview {
  roles: number;
  intros_sent: number;
  intros_accepted: number;
  shortlist_total: number;
  shortlist_funnel: Record<string, number>;
  hires: number;
  tier: string;
}

export type ShortlistStage =
  | "shortlisted" | "contacted" | "interviewing" | "offer" | "hired" | "passed";

export interface TalentCard {
  user_id: string;
  headline: string | null;
  location: string | null;
  seniority: string | null;
  years_experience: number | null;
  top_skills: string[];
  compensation: string | null;
  work_pref: string | null;
  identity_verified: boolean;
  saved?: boolean;
  stage?: ShortlistStage;
  note?: string | null;
}

export interface PublicCompany {
  name: string;
  website: string | null;
  industry: string | null;
  size: string | null;
  location: string | null;
  about: string | null;
  logo_url: string | null;
  roles: { id: number; title: string; location: string; remote: boolean }[];
}

export interface CvFix {
  title: string;
  detail: string;
  quote: string;
}

export interface CvAssessment {
  score: number;
  headline: string;
  fixes: CvFix[];
}

export interface CredentialAssessment {
  skill: string;
  score: number | null;
  verdict: "verified" | "needs_review" | "failed" | null;
  method?: string | null;
  summary?: string | null;
  taken_at?: string | null;
}

export interface Credential {
  identity_verified: boolean;
  identity_method?: string | null;
  assessment: CredentialAssessment | null;
}

export interface AssessmentTask {
  assessment_id: string;
  skill: string;
  questions: string[];
  time_limit_seconds: number;
  seconds_remaining: number;
}

export interface AssessmentResult {
  score: number;
  verdict: "verified" | "needs_review" | "failed";
  summary: string | null;
}

export interface AssessmentIntegrity {
  tab_switches: number;
  blur_seconds: number;
  paste_events: number;
  mode?: "written" | "voice_video";
  camera_present?: boolean;
  face_absent_seconds?: number;
}

export interface AppNotification {
  id: string;
  kind: string;
  title: string;
  body: string | null;
  link: string | null;
  read: boolean;
  created_at: string;
}

export interface NotificationsOut {
  unread: number;
  items: AppNotification[];
}

export interface NotificationPrefs {
  email: boolean;
  whatsapp: boolean;
  digest: boolean;
}

export interface Memory {
  id: number;
  content: string;
  created_at: string;
}

export interface UploadedDoc {
  id: number;
  filename: string;
  size_bytes: number;
  archived: boolean;
  created_at: string;
}

export interface UploadedDocDetail extends UploadedDoc {
  cv_text: string;
}

export type ApplicationStatus = "preparing" | "submitted" | "needs_attention" | "failed";

export interface ApplicationSummary {
  id: string;
  job_id: number;
  title: string;
  company: string;
  location: string;
  status: ApplicationStatus;
  detail: string | null;
  submitted_at: string | null;
  created_at: string;
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

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

// ── admin dashboard types ──
export interface AdminOverview {
  users_total: number;
  users_by_type: Record<string, number>;
  runs_total: number;
  runs_by_status: Record<string, number>;
  subscriptions_active: number;
  subscriptions_by_tier: Record<string, number>;
  jobs_total: number;
  jobs_embedded: number;
  applications_total: number;
  applications_submitted: number;
  intros_total: number;
  intros_accepted: number;
  identity_verified: number;
  assessments_verified: number;
  revenue: { currency: string; amount_minor: number; runs: number }[];
}

export interface AdminUserRow {
  id: string;
  email: string;
  account_type: string;
  company: string | null;
  created_at: string;
  subscription: { tier: string | null; status: string | null } | null;
}

export interface AdminUserDetail extends AdminUserRow {
  is_admin: boolean;
  entitlement: { tier: string; included_runs: boolean; can_apply: boolean; can_voice: boolean };
  profile: {
    full_name: string | null;
    phone: string | null;
    headline: string | null;
    identity_verified: boolean;
    discoverable: boolean;
  } | null;
  credential: { skill: string; score: number | null; verdict: string | null } | null;
  counts: { runs: number; applications: number };
}

export interface AdminRun {
  id: string;
  user_id: string | null;
  target_role: string;
  status: string;
  amount: number;
  currency: string;
  created_at: string;
}

export interface AdminEvent {
  id: number;
  provider: string;
  reference: string;
}

export interface AdminAudit {
  id: number;
  admin_email: string;
  action: string;
  target_user_id: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
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
  me: () => request<MeOut>("/api/auth/me"),
  logout: () => request<{ status: string }>("/api/auth/logout", { method: "POST" }),

  // account type (candidate <-> employer)
  setAccount: (account_type: "candidate" | "employer", company: string | null) =>
    request<MeOut>("/api/account", {
      method: "PUT",
      body: JSON.stringify({ account_type, company }),
    }),

  // candidate insights + employer-discovery consent
  getInsights: () => request<InsightsOut>("/api/candidate/insights"),
  setDiscoverable: (discoverable: boolean) =>
    request<{ discoverable: boolean }>("/api/candidate/discoverable", {
      method: "PUT",
      body: JSON.stringify({ discoverable }),
    }),

  // free public CV assessment (no auth)
  assessCv: (cv_text: string, target_role: string | null) =>
    request<CvAssessment>("/api/assess", {
      method: "POST",
      body: JSON.stringify({ cv_text, target_role }),
    }),
  // Extract text from an uploaded CV (PDF/DOCX/TXT) — no auth, nothing stored.
  extractCv: async (file: File): Promise<{ cv_text: string }> => {
    const body = new FormData();
    body.append("file", file);
    const res = await fetch("/api/assess/extract", {
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
    return res.json() as Promise<{ cv_text: string }>;
  },

  // verification credential (proctored assessment + identity attestation)
  myCredential: () => request<Credential>("/api/assessment"),
  activeAssessment: () =>
    request<{ active: AssessmentTask | null }>("/api/assessment/active"),
  startAssessment: (skill: string) =>
    request<AssessmentTask>("/api/assessment/start", {
      method: "POST",
      body: JSON.stringify({ skill }),
    }),
  submitAssessment: (
    assessment_id: string,
    answers: string[],
    integrity: AssessmentIntegrity,
    snapshots: string[] = [],
  ) =>
    request<AssessmentResult>("/api/assessment/submit", {
      method: "POST",
      body: JSON.stringify({ assessment_id, answers, integrity, snapshots }),
    }),
  attestIdentity: () =>
    request<{ identity_verified: boolean; method: string }>(
      "/api/candidate/identity/attest",
      { method: "POST" },
    ),
  identityMethods: () =>
    request<{ kyc_enabled: boolean; id_types: string[] }>("/api/candidate/identity/methods"),
  verifyIdentity: (id_type: string, id_number: string, dob: string | null) =>
    request<{ identity_verified: boolean; method: string }>(
      "/api/candidate/identity/verify",
      { method: "POST", body: JSON.stringify({ id_type, id_number, dob }) },
    ),

  // intros an employer sent the candidate — the candidate side of the loop
  candidateIntros: () => request<CandidateIntro[]>("/api/candidate/intros"),
  respondIntro: (introId: string, action: "accept" | "decline") =>
    request<{ status: string }>(`/api/candidate/intros/${introId}/respond`, {
      method: "POST",
      body: JSON.stringify({ action }),
    }),

  // employer (Uche)
  postJob: (body: {
    title: string;
    company: string;
    location: string;
    description: string;
    remote: boolean;
    url?: string | null;
  }) => request<EmployerJob>("/api/employer/jobs", { method: "POST", body: JSON.stringify(body) }),
  employerJobs: () => request<EmployerJob[]>("/api/employer/jobs"),
  curatedCandidates: (jobId: number) =>
    request<Shortlist>(`/api/employer/jobs/${jobId}/candidates`),
  requestIntro: (job_id: number, candidate_id: string, message: string | null) =>
    request<{ intro_id: string; status: string; already_requested: boolean }>(
      "/api/employer/intros",
      { method: "POST", body: JSON.stringify({ job_id, candidate_id, message }) },
    ),
  employerIntros: () => request<EmployerIntro[]>("/api/employer/intros"),
  employerPlans: () => request<Plan[]>("/api/employer/plans"),
  employerPlan: () => request<EmployerPlan>("/api/employer/plan"),

  // employer console
  employerOverview: () => request<EmployerOverview>("/api/employer/overview"),
  getCompany: () => request<CompanyProfile | null>("/api/employer/company"),
  putCompany: (body: CompanyProfile) =>
    request<CompanyProfile>("/api/employer/company", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  publicCompany: (id: string) => request<PublicCompany>(`/api/company/${id}`),
  searchTalent: (params: {
    q?: string;
    location?: string;
    seniority?: string;
    verified?: boolean;
  }) => {
    const qs = new URLSearchParams();
    if (params.q) qs.set("q", params.q);
    if (params.location) qs.set("location", params.location);
    if (params.seniority) qs.set("seniority", params.seniority);
    if (params.verified) qs.set("verified", "true");
    return request<{ candidates: TalentCard[] }>(`/api/employer/candidates?${qs}`);
  },
  saveToShortlist: (candidate_id: string, job_id: number | null, note: string | null) =>
    request<{ ok: boolean; stage: string }>("/api/employer/shortlist", {
      method: "POST",
      body: JSON.stringify({ candidate_id, job_id, note }),
    }),
  getShortlist: () =>
    request<{ funnel: Record<string, number>; candidates: TalentCard[] }>(
      "/api/employer/shortlist",
    ),
  updateShortlist: (candidate_id: string, stage: ShortlistStage | null, note: string | null) =>
    request<{ ok: boolean }>(`/api/employer/shortlist/${candidate_id}`, {
      method: "PUT",
      body: JSON.stringify({ stage, note }),
    }),
  removeFromShortlist: (candidate_id: string) =>
    request<{ ok: boolean }>(`/api/employer/shortlist/${candidate_id}`, { method: "DELETE" }),

  // notifications (in-app centre; email + WhatsApp fan out server-side)
  notifications: () => request<NotificationsOut>("/api/notifications"),
  markNotificationsRead: (id?: string) =>
    request<{ ok: boolean }>("/api/notifications/read", {
      method: "POST",
      body: JSON.stringify({ id: id ?? null }),
    }),
  getNotificationPrefs: () =>
    request<NotificationPrefs>("/api/notifications/preferences"),
  setNotificationPrefs: (prefs: NotificationPrefs) =>
    request<NotificationPrefs>("/api/notifications/preferences", {
      method: "PUT",
      body: JSON.stringify(prefs),
    }),
  unsubscribe: (token: string) =>
    request<{ ok: boolean }>("/api/notifications/unsubscribe", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),

  // web push
  getVapidKey: () => request<{ key: string }>("/api/push/vapid-public-key"),
  pushSubscribe: (sub: PushSubscriptionJSON) =>
    request<{ status: string }>("/api/push/subscribe", {
      method: "POST",
      body: JSON.stringify(sub),
    }),
  pushUnsubscribe: (endpoint: string) =>
    request<{ status: string }>("/api/push/unsubscribe", {
      method: "POST",
      body: JSON.stringify({ endpoint }),
    }),

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

  // chat history — the rolling Ask Ada conversation
  chatHistory: () => request<ChatMessage[]>("/api/chat/history"),
  clearChatHistory: () =>
    fetch("/api/chat/history", { method: "DELETE", credentials: "same-origin" }).then((r) => {
      if (!r.ok) throw new ApiError(r.status, r.statusText);
    }),

  // memories — what Ada remembers about the user from chats
  listMemories: () => request<Memory[]>("/api/memories"),
  deleteMemory: (id: number) =>
    fetch(`/api/memories/${id}`, { method: "DELETE", credentials: "same-origin" }).then((r) => {
      if (!r.ok) throw new ApiError(r.status, r.statusText);
    }),

  // documents
  listDocuments: () => request<UploadedDoc[]>("/api/documents"),
  getDocument: (id: number) => request<UploadedDocDetail>(`/api/documents/${id}`),
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
    return res.json() as Promise<{
      id: number;
      cv_text: string;
      gcs_uri: string | null;
      filename: string;
    }>;
  },

  // applications
  applyToJob: (jobId: number, runId?: string) =>
    request<{ application_id: string; status: ApplicationStatus; already_applied: boolean }>(
      `/api/jobs/${jobId}/apply`,
      { method: "POST", body: JSON.stringify({ run_id: runId ?? null }) },
    ),
  listApplications: () => request<ApplicationSummary[]>("/api/applications"),

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
  putIdentity: (fields: {
    full_name: string;
    phone: string | null;
    compensation?: string | null;
    work_pref?: string | null;
  }) =>
    request<Profile>("/api/profile/identity", {
      method: "PUT",
      body: JSON.stringify(fields),
    }),

  // subscriptions
  getPlans: () => request<Plan[]>("/api/plans"),
  getSubscription: () => request<SubscriptionState>("/api/subscription"),
  startSubscription: (tier: string, cadence: string, provider: "paystack" | "stripe") =>
    request<{ checkout_url: string }>("/api/subscriptions", {
      method: "POST",
      body: JSON.stringify({ tier, cadence, provider }),
    }),
  cancelSubscription: () =>
    request<{ status: string }>("/api/subscriptions/cancel", { method: "POST" }),

  // profile
  getProfile: () => request<Profile | null>("/api/profile"),
  putProfile: (body: { profile_text: string; linkedin_url?: string | null }) =>
    request<Profile>("/api/profile", { method: "PUT", body: JSON.stringify(body) }),

  // ── admin dashboard (gated server-side by the ADMIN_EMAILS allowlist) ──
  admin: {
    me: () => request<{ email: string; admin: boolean }>("/api/admin/me"),
    overview: () => request<AdminOverview>("/api/admin/overview"),
    users: (q: string, limit = 50, offset = 0) =>
      request<AdminUserRow[]>(
        `/api/admin/users?q=${encodeURIComponent(q)}&limit=${limit}&offset=${offset}`,
      ),
    user: (id: string) => request<AdminUserDetail>(`/api/admin/users/${id}`),
    setAccountType: (id: string, account_type: "candidate" | "employer") =>
      request<{ ok: boolean }>(`/api/admin/users/${id}/account-type`, {
        method: "PUT",
        body: JSON.stringify({ account_type }),
      }),
    grant: (id: string, tier: string, cadence: string, days: number) =>
      request<{ ok: boolean; tier: string; until: string }>(`/api/admin/users/${id}/subscription`, {
        method: "POST",
        body: JSON.stringify({ tier, cadence, days }),
      }),
    revoke: (id: string) =>
      request<{ ok: boolean }>(`/api/admin/users/${id}/subscription`, { method: "DELETE" }),
    deleteUser: (id: string) =>
      request<{ ok: boolean }>(`/api/admin/users/${id}`, { method: "DELETE" }),
    impersonate: (id: string) =>
      request<{ ok: boolean; impersonating: string }>(`/api/admin/users/${id}/impersonate`, {
        method: "POST",
      }),
    runs: (status: string, limit = 50) =>
      request<AdminRun[]>(`/api/admin/runs?status=${status}&limit=${limit}`),
    redispatch: (id: string) =>
      request<{ ok: boolean }>(`/api/admin/runs/${id}/redispatch`, { method: "POST" }),
    events: (limit = 100) => request<AdminEvent[]>(`/api/admin/events?limit=${limit}`),
    ingest: () => request<{ ok: boolean; message: string }>("/api/admin/jobs/ingest", { method: "POST" }),
    embed: () => request<{ ok: boolean; message: string }>("/api/admin/jobs/embed", { method: "POST" }),
    broadcast: (title: string, body: string, link: string | null, account_type: string | null) =>
      request<{ ok: boolean; recipients: number }>("/api/admin/broadcast", {
        method: "POST",
        body: JSON.stringify({ title, body, link, account_type }),
      }),
    audit: (limit = 100) => request<AdminAudit[]>(`/api/admin/audit?limit=${limit}`),
  },
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

/** Backend WebSocket base for talking to Ada (rewrites don't proxy upgrades). */
export function voiceWsUrl(mode?: "conversation" | "interview"): string {
  const base =
    process.env.NEXT_PUBLIC_WS_URL ??
    (typeof window !== "undefined"
      ? `${window.location.protocol === "https:" ? "wss" : "ws"}://localhost:8080`
      : "ws://localhost:8080");
  const query = mode === "interview" ? "?mode=interview" : "";
  return `${base}/api/voice${query}`;
}
