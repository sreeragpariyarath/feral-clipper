"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useRef, useState } from "react";
import { ArrowLeft, Download, Trash2 } from "lucide-react";
import { DecisionButtons } from "@/components/clips/DecisionButtons";
import { JudgeNotes } from "@/components/clips/JudgeNotes";
import { ReviewEditor } from "@/components/clips/ReviewEditor";
import { ScoreBars } from "@/components/clips/ScoreBars";
import { Transcript } from "@/components/clips/Transcript";
import { StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, ErrorNote, Skeleton } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { downloadUrl } from "@/lib/api";
import { clock, streamName } from "@/lib/format";
import { useClipDetails, useTrashClip } from "@/lib/queries";

export default function ClipPage({ params }: { params: Promise<{ id: string }> }) {
  const id = Number(use(params).id);
  const router = useRouter();
  const toast = useToast();
  const { data, isLoading, error } = useClipDetails(id);
  const trash = useTrashClip();
  const video = useRef<HTMLVideoElement>(null);
  const [time, setTime] = useState(0);

  if (isLoading) return <Skeleton className="h-[32rem]" />;
  if (!data) return <ErrorNote error={error ?? "Clip not found"} />;

  const { clip, judge, words, score } = data;
  const offset = judge.start_s ?? 0;
  const dl = downloadUrl(clip);
  const window = score ? `${clock(score.start)}–${clock(score.end)} in the stream` : "";

  const onTrash = () => {
    if (!confirm("Move this clip to the trash? You can restore it from the Trash page.")) return;
    trash.mutate(clip.id, { onSuccess: () => { toast.ok("Moved to trash"); router.push("/clips"); }, onError: toast.error });
  };

  return (
    <>
      <Link href={`/clips?stream=${encodeURIComponent(clip.stream_id)}`} className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft size={14} /> Clips
      </Link>
      <PageHeader
        title={clip.title || `Clip ${clip.clip_no}`}
        subtitle={<span className="flex flex-wrap items-center gap-2 capitalize">{streamName(clip.stream_id)} · #{clip.clip_no} {window && `· ${window}`} <StatusBadge status={clip.status} /></span>}
        actions={
          <>
            {clip.has_video && <DecisionButtons clip={clip} size="md" />}
            {dl && <a href={dl} download><Button variant="primary"><Download size={16} /> Download</Button></a>}
            {!clip.deleted && <Button variant="danger" size="icon" aria-label="Move to trash" onClick={onTrash}><Trash2 size={16} /></Button>}
          </>
        }
      />

      <div className="grid gap-5 lg:grid-cols-[minmax(0,22rem)_1fr]">
        <div className="lg:sticky lg:top-6 lg:self-start">
          <Card className="overflow-hidden bg-black">
            {clip.video_url
              ? <video ref={video} src={clip.video_url} poster={clip.thumb_url ?? undefined} controls playsInline
                  onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)} className="aspect-[9/16] w-full" />
              : <div className="aspect-[9/16]"><EmptyState title="Not rendered">Claude skipped this moment.</EmptyState></div>}
          </Card>
        </div>

        <div className="grid content-start gap-5">
          <ReviewEditor clip={clip} />
          <JudgeNotes judge={judge} />
          <Transcript words={words} offset={offset} time={time}
            onSeek={(t) => { if (video.current) { video.current.currentTime = Math.max(0, t); void video.current.play(); } }} />
          <ScoreBars row={score} judgeScore={judge.score} />
          {data.strip_url && (
            <Card className="overflow-hidden">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={data.strip_url} alt="Six frames from the moment" className="w-full" />
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
