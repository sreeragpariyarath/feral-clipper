import type { Clip, Decision } from "../../lib/types";
import { ClipCard } from "./ClipCard";

type Props = {
  clips: Clip[];
  session: string;
  busy: boolean;
  onReview: (clip: Clip, decision: Decision) => void;
};

export function ClipGrid({ clips, session, busy, onReview }: Props) {
  return (
    <section aria-label="Clips" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {clips.map((clip) => (
        <ClipCard key={clip.id} clip={clip} session={session} busy={busy} onReview={onReview} />
      ))}
    </section>
  );
}
