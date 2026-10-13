const GATEWAY = process.env.NEXT_PUBLIC_GATEWAY_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("hirefit_token");
}

export function setToken(token: string): void {
  localStorage.setItem("hirefit_token", token);
}

export function clearToken(): void {
  localStorage.removeItem("hirefit_token");
}

async function api<T>(path: string, init?: RequestInit, auth = true): Promise<T> {
  const headers: Record<string, string> = { ...((init?.headers as Record<string, string>) ?? {}) };
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  if (init?.body && !(init.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const res = await fetch(`${GATEWAY}${path}`, { ...init, headers });
  if (!res.ok) throw new ApiError(res.status, (await res.text()).slice(0, 500));
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export interface User {
  id: string;
  email: string;
  role: string;
}

export interface Job {
  id: string;
  title: string;
  description: string;
  skills: string[];
  created_by: string;
}

export interface ResumeStatus {
  resume_id: string;
  filename: string;
  size_bytes: number;
  status: string;
  s3_key: string;
  has_parsed: boolean;
  parsed: Record<string, string> | null;
}

export interface MatchResult {
  resume_id: string;
  job_id: string;
  ret_score: number | null;
  ce_score: number;
  skill_score: number;
  final_score: number;
  matched_skills: string[];
  missing_skills: string[];
}

export interface ExplainResult {
  log_id: string;
  kind: string;
  model: string;
  citations: string[];
  output: string;
}

export const register = (email: string, password: string, role: string): Promise<User> =>
  api("/api/v1/auth/register", { method: "POST", body: JSON.stringify({ email, password, role }) }, false);

export const login = (email: string, password: string): Promise<{ access_token: string; refresh_token: string }> =>
  api("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }, false);

export const me = (): Promise<User> => api("/api/v1/auth/me");

export const uploadResume = (file: File): Promise<{ resume_id: string; status: string }> => {
  const form = new FormData();
  form.append("file", file);
  return api("/api/v1/resumes/upload", { method: "POST", body: form });
};

export const getResume = (id: string): Promise<ResumeStatus> => api(`/api/v1/resumes/${id}`, {}, false);

export const createJob = (title: string, description: string, skills: string[]): Promise<Job> =>
  api("/api/v1/jobs", { method: "POST", body: JSON.stringify({ title, description, skills }) });

export const listJobs = (q = ""): Promise<Job[]> => api(`/api/v1/jobs?q=${encodeURIComponent(q)}`);

export const matchSingle = (resume_id: string, job_id: string): Promise<MatchResult> =>
  api("/api/v1/match/single", { method: "POST", body: JSON.stringify({ resume_id, job_id }) });

export const matchBulk = (job_id: string, top_k = 50, limit = 20): Promise<{ job_id: string; matches: MatchResult[] }> =>
  api(`/api/v1/match/job/${job_id}`, { method: "POST", body: JSON.stringify({ top_k, limit }) });

export const explain = (resume_id: string, job_id: string, kind: string): Promise<ExplainResult> =>
  api("/api/v1/explain", { method: "POST", body: JSON.stringify({ resume_id, job_id, kind }) });

export const gateway = GATEWAY;
