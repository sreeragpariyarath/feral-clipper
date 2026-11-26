import { Download, Trash2 } from "lucide-react";
import type { Clip, Decision } from "../../lib/types";
import { mediaBase } from "../../lib/api";
import { Button } from "../ui/Button";

const ACTIONS: { decision: Decision; label: string }[] = [
  { decision: "approved", label: "Approve" },
  { decision: "rejected", label: "Reject" },
  { decision: "pending", label: "Reset" },
];

type Props = {
  clip: Clip;
  session: string;
  busy: boolean;
  onReview: (clip: Clip, decision: Decision) => void;
  onDelete: (clip: Clip) => void;
};

export function ClipCard({ clip, session, busy, onReview, onDelete }: Props) {
  const media = mediaBase(session, clip.id);
  return (
    <article className="overflow-hidden rounded-2xl border bg-card shadow-sm">
      {clip.has_video && (
        <video
          src={media + "/clip.mp4"}
          poster={media + "/thumb.jpg"}
          controls
          playsInline
          preload="none"
          className="aspect-[9/16] max-h-96 w-full bg-black object-contain"
        />
      )}
      <div className="space-y-3 p-4">
        <h2 className="font-semibold">{clip.title || "Clip " + clip.id}</h2>
        <p className="w-fit rounded-full bg-muted px-2.5 py-1 text-xs font-medium capitalize text-muted-foreground">
          {clip.decision === "pending" ? "To review" : clip.decision}
        </p>
        <div className="flex flex-wrap gap-2 text-sm">
          {clip.has_video && (
            <a download href={media + "/clip.mp4"} className="inline-flex items-center gap-1 rounded-lg border px-2 py-1">
              <Download size={13} />
              Download
            </a>
          )}
          {ACTIONS.map((action) => (
            <Button
              key={action.decision}
              disabled={busy || clip.decision === action.decision}
              onClick={() => onReview(clip, action.decision)}
            >
              {action.label}
            </Button>
          ))}
          <Button disabled={busy} onClick={() => onDelete(clip)} className="inline-flex items-center gap-1 whitespace-nowrap text-red-500 hover:text-red-400">
            <Trash2 size={13} />
            Delete
          </Button>
        </div>
      </div>
    </article>
  );
}
