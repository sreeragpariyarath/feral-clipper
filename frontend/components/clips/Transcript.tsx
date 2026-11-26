"use client";

import type { Word } from "@/lib/types";
import { clock } from "@/lib/format";
import { Card, CardHeader } from "../ui/Card";
import { cn } from "../ui/cn";

/** Transcript of the cut window. The word under the playhead is highlighted; click a word to jump there. */
export function Transcript({ words, offset, time, onSeek }: {
  words: Word[];
  offset: number;          // window time where the rendered clip starts
  time: number;            // current player time
  onSeek: (t: number) => void;
}) {
  const now = time + offset;
  return (
    <Card>
      <CardHeader title="Transcript" subtitle={`${words.length} words`} />
      <p className="max-h-64 overflow-y-auto p-4 text-sm leading-7">
        {words.map((w, i) => {
          const inClip = w.s >= offset - 0.05;
          const active = now >= w.s && now < w.e;
          return (
            <button key={i} type="button" title={clock(w.s)} disabled={!inClip} onClick={() => onSeek(w.s - offset)}
              className={cn("rounded px-0.5 transition", active ? "bg-primary text-primary-foreground" : inClip ? "hover:bg-muted" : "text-muted-foreground/50")}>
              {w.w}
            </button>
          );
        })}
        {!words.length && <span className="text-muted-foreground">No words found.</span>}
      </p>
    </Card>
  );
}
