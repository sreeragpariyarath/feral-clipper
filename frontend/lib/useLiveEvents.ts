"use client";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { keys } from "./queries";
import type { ActivityEvent } from "./types";

export type LiveState = "connecting" | "live" | "offline";

const EVENTS_URL = (process.env.NEXT_PUBLIC_API_ORIGIN ?? "http://127.0.0.1:8766") + "/api/v1/events";

/**
 * Opens one Server-Sent Events connection for the whole app and turns each event into cache refreshes.
 * Progress events update the job in place (no refetch), so a running step moves smoothly.
 */
export function useLiveEvents(): LiveState {
  const qc = useQueryClient();
  const [state, setState] = useState<LiveState>("connecting");

  useEffect(() => {
    // Straight to the API: the Next dev proxy buffers streamed responses, which would hold events back.
    const source = new EventSource(EVENTS_URL);
    const pending = new Set<string>();
    let timer: ReturnType<typeof setTimeout> | undefined;

    // Many events arrive in bursts; batch refetches to at most one every 400 ms per key.
    const refresh = (...list: (readonly unknown[])[]) => {
      list.forEach((k) => pending.add(JSON.stringify(k)));
      clearTimeout(timer);
      timer = setTimeout(() => {
        pending.forEach((k) => qc.invalidateQueries({ queryKey: JSON.parse(k) }));
        pending.clear();
      }, 400);
    };

    const onEvent = (e: MessageEvent) => {
      const ev: ActivityEvent = JSON.parse(e.data);
      qc.setQueryData<ActivityEvent[]>(keys.activity, (old) => [ev, ...(old ?? [])].slice(0, 60));
      const jobId = ev.job_id ?? 0;
      if (ev.kind === "progress" && jobId) {
        refresh(keys.job(jobId), keys.jobs);
      } else if (ev.kind === "step" || ev.kind === "job") {
        refresh(keys.job(jobId), keys.jobs, keys.health, keys.streams, keys.clipsAll);
      } else if (ev.kind === "clip") {
        refresh(keys.clipsAll, keys.streams);
      }
    };

    source.onopen = () => setState("live");
    source.onerror = () => setState(source.readyState === EventSource.CLOSED ? "offline" : "connecting");
    for (const kind of ["progress", "step", "job", "clip", "info"]) source.addEventListener(kind, onEvent);
    return () => {
      clearTimeout(timer);
      source.close();
    };
  }, [qc]);

  return state;
}
