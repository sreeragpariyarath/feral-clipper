/** Shapes returned by the /api/v1 backend (mirrors backend/schemas). */

export type Decision = "pending" | "approved" | "rejected";
export type JobKind = "download" | "monitor" | "render";
export type JobStatus = "creating" | "queued" | "running" | "done" | "failed" | "cancelled";
export type StepStatus = "pending" | "running" | "done" | "failed" | "cancelled" | "skipped";

export type Health = {
  ok: boolean;
  keys: Record<string, boolean>;
  running_job: number | null;
  queued_jobs: number;
  disk: { free_gb: number; total_gb: number; low_below_gb?: number };
  low_disk: boolean;
};

export type Stream = {
  id: string;
  title: string;
  channel: string;
  source_url: string;
  duration_s: number;
  video_file: string;
  size_gb: number;
  clips: number;
  ready: number;
  approved: number;
  updated_at: string;
};

export type Clip = {
  id: number;
  stream_id: string;
  clip_no: string;
  status: string;
  final_score: number;
  strong: boolean;
  title: string;
  caption: string;
  hook: string;
  reasons: string;
  judge_source: string;
  decision: Decision;
  deleted: boolean;
  has_video: boolean;
  video_url: string | null;
  thumb_url: string | null;
  updated_at: string;
};

export type Word = { w: string; s: number; e: number };

export type ScoreRow = {
  no: string;
  start: number;
  end: number;
  monitor: number;
  final: number;
  sub: Record<string, number>;
  hook: { hook_line?: string; hook_score?: number; reaction?: number; reaction_labels?: string[] };
  visual: { action?: number | null; boring?: number | null; unsafe?: number | null; best?: string };
  notes: string[];
};

export type ClipDetail = {
  clip: Clip;
  judge: {
    title?: string;
    hook_text?: string;
    category?: string;
    score?: number;
    reasons?: string;
    violations?: string[];
    needs_context?: boolean;
    start_s?: number;
    end_s?: number;
    source?: string;
  };
  words: Word[];
  score: ScoreRow | null;
  face_box: unknown;
  strip_url: string | null;
};

export type ClipPatch = Partial<Pick<Clip, "decision" | "title" | "caption">>;

export type Step = {
  idx: number;
  name: string;
  label: string;
  status: StepStatus;
  progress: number | null;
  message: string;
  eta: string;
  started_at: string | null;
  finished_at: string | null;
};

export type Job = {
  id: number;
  kind: JobKind;
  source_url: string;
  stream_id: string;
  params: Record<string, unknown>;
  results: Record<string, Record<string, unknown>>;
  tokens: { in: number; out: number };
  status: JobStatus;
  current_step: string;
  error: string;
  error_hint: string;
  cancel_requested: boolean;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  progress: { percent: number | null; text: string; eta: string };
  steps: Step[];
  log: string[] | null;
};

export type JobCreate = { kind: JobKind; url?: string; path?: string; top: number; campaign_id?: number | null };

export type Campaign = {
  id: number;
  name: string;
  streamer: string;
  active: boolean;
  brief: string;
  caption: string;
  logo_path: string;
  payout_per_1k: number;
  platforms: string[];
  ends_at: string | null;
  logo_on: boolean;
  logo_width: number;
  logo_y: number;
  hashtags: string;
  created_at: string;
};
export type CampaignIn = Omit<Campaign, "id" | "created_at">;

export type ActivityEvent = {
  id: number;
  job_id: number | null;
  kind: string;
  message: string;
  data: Record<string, unknown>;
  created_at: string;
};

export type Settings = { keys: Record<string, boolean>; values: Record<string, unknown> };

export type Platform = "youtube" | "tiktok" | "instagram" | "other";

export type Post = {
  id: number;
  clip_id: number;
  campaign_id: number | null;
  campaign_name: string | null;
  platform: Platform;
  url: string;
  title: string;
  posted_at: string;
  views: number;
  views_at: string | null;
  payout_usd: number | null;
  clip_title: string;
  thumb_url: string | null;
};
export type PostIn = { clip_id: number; platform: Platform; url?: string; title?: string; posted_at?: string | null };

export type PlatformKit = { platform: Platform; title: string; caption: string; hashtags: string[]; limit_note: string };
export type PostingKit = {
  clip_id: number;
  campaign_name: string | null;
  platforms: PlatformKit[];
  best_times_local: string[];
  best_times_note: string;
  thumb_url: string | null;
};

export type Backup = { name: string; size_mb: number; created_at: string };
