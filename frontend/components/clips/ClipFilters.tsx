"use client";

import { useStreams } from "@/lib/queries";
import { streamName } from "@/lib/format";
import { Select } from "../ui/Field";
import { Tabs } from "../ui/Tabs";

export type ClipView = "ready" | "approved" | "rejected" | "skipped" | "all";
export type ClipSort = "score" | "newest";

type Props = {
  stream: string;
  onStream: (s: string) => void;
  view: ClipView;
  onView: (v: ClipView) => void;
  sort: ClipSort;
  onSort: (s: ClipSort) => void;
  counts: Record<ClipView, number>;
};

export function ClipFilters({ stream, onStream, view, onView, sort, onSort, counts }: Props) {
  const { data: streams = [] } = useStreams();
  return (
    <div className="mb-5 flex flex-wrap items-center gap-3">
      <Tabs<ClipView> value={view} onChange={onView}
        tabs={(["ready", "approved", "rejected", "skipped", "all"] as ClipView[]).map((v) => ({
          value: v, label: v[0].toUpperCase() + v.slice(1), count: counts[v],
        }))} />
      <Select aria-label="Stream" value={stream} onChange={(e) => onStream(e.target.value)} className="w-auto min-w-48">
        <option value="">All streams</option>
        {streams.map((s) => <option key={s.id} value={s.id}>{s.title || streamName(s.id)} ({s.clips})</option>)}
      </Select>
      <Select aria-label="Sort" value={sort} onChange={(e) => onSort(e.target.value as ClipSort)} className="w-auto">
        <option value="score">Best score first</option>
        <option value="newest">Newest first</option>
      </Select>
    </div>
  );
}
