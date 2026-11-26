"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { CampaignIn, ClipPatch, Decision, JobCreate, PostIn } from "./types";

/** One place for every cache key, so live events know what to refresh. */
export const keys = {
  health: ["health"] as const,
  settings: ["settings"] as const,
  streams: ["streams"] as const,
  clips: (f: object = {}) => ["clips", f] as const,
  clipsAll: ["clips"] as const,
  clip: (id: number) => ["clip", id] as const,
  jobs: ["jobs"] as const,
  job: (id: number) => ["job", id] as const,
  campaigns: ["campaigns"] as const,
  activity: ["activity"] as const,
  posts: ["posts"] as const,
  kit: (id: number) => ["kit", id] as const,
  backups: ["backups"] as const,
};

export const useHealth = () => useQuery({ queryKey: keys.health, queryFn: api.health });
export const useSettings = () => useQuery({ queryKey: keys.settings, queryFn: api.settings });
export const useStreams = () => useQuery({ queryKey: keys.streams, queryFn: api.streams });
export const useJobs = () => useQuery({ queryKey: keys.jobs, queryFn: () => api.jobs(50) });
export const useJob = (id: number) => useQuery({ queryKey: keys.job(id), queryFn: () => api.job(id), enabled: id > 0 });
export const useCampaigns = () => useQuery({ queryKey: keys.campaigns, queryFn: api.campaigns });
export const useActivity = () => useQuery({ queryKey: keys.activity, queryFn: () => api.activity(40) });

export function useClips(f: { stream_id?: string; decision?: Decision; deleted?: boolean } = {}) {
  return useQuery({ queryKey: keys.clips(f), queryFn: () => api.clips(f) });
}

export function useClipDetails(id: number) {
  return useQuery({ queryKey: keys.clip(id), queryFn: () => api.clipDetails(id), enabled: id > 0 });
}

function useInvalidate() {
  const qc = useQueryClient();
  return (...list: (readonly unknown[])[]) => Promise.all(list.map((k) => qc.invalidateQueries({ queryKey: k })));
}

export function usePatchClip() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: ClipPatch }) => api.patchClip(id, patch),
    onSuccess: (c) => inv(keys.clipsAll, keys.clip(c.id), keys.streams),
  });
}

export function useTrashClip() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: api.trashClip, onSuccess: (c) => inv(keys.clipsAll, keys.clip(c.id), keys.streams) });
}

export function useRestoreClip() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: api.restoreClip, onSuccess: (c) => inv(keys.clipsAll, keys.clip(c.id), keys.streams) });
}

export function useCreateJob() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: (b: JobCreate) => api.createJob(b), onSuccess: () => inv(keys.jobs, keys.health) });
}

export function useJobAction(kind: "cancel" | "retry") {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (id: number) => (kind === "cancel" ? api.cancelJob(id) : api.retryJob(id)),
    onSuccess: (j) => inv(keys.jobs, keys.job(j.id), keys.health),
  });
}

export function useSaveCampaign() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ id, body }: { id?: number; body: CampaignIn }) =>
      id ? api.updateCampaign(id, body) : api.createCampaign(body),
    onSuccess: () => inv(keys.campaigns),
  });
}

export function useDeleteCampaign() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: api.deleteCampaign, onSuccess: () => inv(keys.campaigns) });
}

export const usePosts = (clipId?: number) =>
  useQuery({ queryKey: [...keys.posts, clipId ?? "all"], queryFn: () => api.posts(clipId) });
export const usePostingKit = (clipId: number) =>
  useQuery({ queryKey: keys.kit(clipId), queryFn: () => api.postingKit(clipId), enabled: clipId > 0 });

export function useCreatePost() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: (p: PostIn) => api.createPost(p), onSuccess: () => inv(keys.posts) });
}

export function useUpdatePost() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: { views?: number; url?: string } }) => api.updatePost(id, patch),
    onSuccess: () => inv(keys.posts),
  });
}

export function useDeletePost() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: api.deletePost, onSuccess: () => inv(keys.posts) });
}

export const useBackups = () => useQuery({ queryKey: keys.backups, queryFn: api.backups });

export function useMakeBackup() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: api.makeBackup, onSuccess: () => inv(keys.backups) });
}

export function useDeleteStreamVideo() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: api.deleteStreamVideo, onSuccess: () => inv(keys.streams, keys.health) });
}
