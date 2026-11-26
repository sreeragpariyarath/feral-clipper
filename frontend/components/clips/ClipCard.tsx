import Link from "next/link";
import { Film } from "lucide-react";
import type { Clip } from "@/lib/types";
import { Badge, StatusBadge } from "../ui/Badge";
import { DecisionButtons } from "./DecisionButtons";
import { ScoreRing } from "./ScoreRing";

export function ClipCard({ clip }: { clip: Clip }) {
  return (
    <article className="group overflow-hidden rounded-xl border bg-card transition hover:border-primary/40 hover:shadow-md">
      <Link href={`/clips/${clip.id}`} className="relative block aspect-[9/16] max-h-80 w-full overflow-hidden bg-zinc-900">
        {clip.thumb_url
          // eslint-disable-next-line @next/next/no-img-element
          ? <img src={clip.thumb_url} alt="" loading="lazy" className="size-full object-cover transition group-hover:scale-[1.02]" />
          : <div className="grid size-full place-items-center text-zinc-500"><Film /><span className="text-xs">not rendered</span></div>}
        <div className="absolute top-2 right-2 rounded-full bg-black/60 text-white backdrop-blur"><ScoreRing value={clip.final_score} size={38} /></div>
        <div className="absolute top-2 left-2 flex gap-1">
          <StatusBadge status={clip.status} />
          {clip.decision !== "pending" && <StatusBadge status={clip.decision} />}
        </div>
      </Link>
      <div className="grid gap-2 p-3">
        <Link href={`/clips/${clip.id}`} className="line-clamp-2 min-h-10 text-sm font-semibold leading-snug hover:underline">
          {clip.title || clip.hook || `Clip ${clip.clip_no}`}
        </Link>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>#{clip.clip_no}</span>
          {clip.judge_source && <Badge>{clip.judge_source.replace("claude-", "")}</Badge>}
        </div>
        {clip.has_video && <DecisionButtons clip={clip} />}
      </div>
    </article>
  );
}
