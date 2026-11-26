import type {
  ActivityEvent, Campaign, CampaignIn, Clip, ClipDetail, ClipPatch, Decision, Health, Job, JobCreate,
  Backup, Post, PostIn, PostingKit, Settings, Stream,
} from "./types";

const BASE = "/api/v1";

/** Error with the backend's `detail` message, so the UI can show it as is. */
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, ...rest } = init ?? {};
  const res = await fetch(BASE + path, {
    ...rest,
    headers: json === undefined ? rest.headers : { "Content-Type": "application/json", ...rest.headers },
    body: json === undefined ? rest.body : JSON.stringify(json),
  });
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      const detail = body?.detail;
      message = typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : message;
    } catch { /* body was not JSON; keep the status message */ }
    throw new ApiError(res.status, message);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

const qs = (params: Record<string, string | number | boolean | undefined | null>) => {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  const s = q.toString();
  return s ? "?" + s : "";
};

export const api = {
  health: () => request<Health>("/health"),
  settings: () => request<Settings>("/settings"),
  saveSettings: (values: Record<string, unknown>) => request<Settings>("/settings", { method: "PUT", json: { values } }),

  streams: () => request<Stream[]>("/streams"),
  deleteStreamVideo: (id: string) =>
    request<{ stream_id: string; freed_gb: number }>(`/streams/${encodeURIComponent(id)}/video`, { method: "DELETE" }),
  backups: () => request<Backup[]>("/backups"),
  makeBackup: () => request<Backup>("/backups", { method: "POST" }),

  clips: (f: { stream_id?: string; decision?: Decision; deleted?: boolean } = {}) => request<Clip[]>("/clips" + qs(f)),
  clipDetails: (id: number) => request<ClipDetail>(`/clips/${id}/details`),
  patchClip: (id: number, patch: ClipPatch) => request<Clip>(`/clips/${id}`, { method: "PATCH", json: patch }),
  trashClip: (id: number) => request<Clip>(`/clips/${id}`, { method: "DELETE" }),
  restoreClip: (id: number) => request<Clip>(`/clips/${id}/restore`, { method: "POST" }),

  jobs: (limit = 30) => request<Job[]>("/jobs" + qs({ limit })),
  job: (id: number) => request<Job>(`/jobs/${id}`),
  createJob: (body: JobCreate) => request<Job>("/jobs", { method: "POST", json: body }),
  cancelJob: (id: number) => request<Job>(`/jobs/${id}/cancel`, { method: "POST" }),
  retryJob: (id: number) => request<Job>(`/jobs/${id}/retry`, { method: "POST" }),

  campaigns: () => request<Campaign[]>("/campaigns"),
  createCampaign: (c: CampaignIn) => request<Campaign>("/campaigns", { method: "POST", json: c }),
  updateCampaign: (id: number, c: CampaignIn) => request<Campaign>(`/campaigns/${id}`, { method: "PUT", json: c }),
  deleteCampaign: (id: number) => request<void>(`/campaigns/${id}`, { method: "DELETE" }),

  posts: (clip_id?: number) => request<Post[]>("/posts" + qs({ clip_id })),
  createPost: (p: PostIn) => request<Post>("/posts", { method: "POST", json: p }),
  updatePost: (id: number, patch: { views?: number; url?: string }) => request<Post>(`/posts/${id}`, { method: "PATCH", json: patch }),
  deletePost: (id: number) => request<void>(`/posts/${id}`, { method: "DELETE" }),
  postingKit: (clipId: number) => request<PostingKit>(`/clips/${clipId}/kit`),

  activity: (limit = 40) => request<ActivityEvent[]>("/activity" + qs({ limit })),
};

/** Link that makes the browser save the clip instead of playing it. */
export const downloadUrl = (clip: Clip) => (clip.video_url ? clip.video_url + "?download=true" : null);
