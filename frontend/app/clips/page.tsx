"use client";

import { Suspense, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Clapperboard } from "lucide-react";
import { ClipCard } from "@/components/clips/ClipCard";
import { ClipFilters, type ClipSort, type ClipView } from "@/components/clips/ClipFilters";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, ErrorNote, Skeleton } from "@/components/ui/States";
import { useClips } from "@/lib/queries";
import type { Clip } from "@/lib/types";

const inView: Record<ClipView, (c: Clip) => boolean> = {
  ready: (c) => c.has_video && c.decision === "pending",
  approved: (c) => c.decision === "approved",
  rejected: (c) => c.decision === "rejected",
  skipped: (c) => !c.has_video,
  all: () => true,
};

function Library() {
  const router = useRouter();
  const params = useSearchParams();
  const stream = params.get("stream") ?? "";
  const [view, setView] = useState<ClipView>("ready");
  const [sort, setSort] = useState<ClipSort>("score");
  const { data: clips = [], isLoading, error } = useClips(stream ? { stream_id: stream } : {});

  const counts = useMemo(() => Object.fromEntries(
    (Object.keys(inView) as ClipView[]).map((v) => [v, clips.filter(inView[v]).length]),
  ) as Record<ClipView, number>, [clips]);

  const shown = useMemo(() => {
    const list = clips.filter(inView[view]);
    return sort === "score"
      ? [...list].sort((a, b) => b.final_score - a.final_score)
      : [...list].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
  }, [clips, view, sort]);

  const setStream = (s: string) => router.replace(s ? `/clips?stream=${encodeURIComponent(s)}` : "/clips");

  return (
    <>
      <PageHeader title="Clips" subtitle="Watch, approve or reject, then download what you'll post." />
      <ClipFilters stream={stream} onStream={setStream} view={view} onView={setView} sort={sort} onSort={setSort} counts={counts} />
      <ErrorNote error={error} />
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {isLoading && [0, 1, 2, 3].map((i) => <Skeleton key={i} className="aspect-[9/16]" />)}
        {shown.map((c) => <ClipCard key={c.id} clip={c} />)}
      </div>
      {!isLoading && !shown.length && (
        <EmptyState icon={<Clapperboard />} title={view === "ready" ? "Nothing waiting for review" : "No clips here"}>
          Start a full run from New job to make more.
        </EmptyState>
      )}
    </>
  );
}

export default function ClipsPage() {
  return <Suspense><Library /></Suspense>;
}
