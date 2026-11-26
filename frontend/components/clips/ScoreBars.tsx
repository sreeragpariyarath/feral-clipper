import type { ScoreRow } from "@/lib/types";
import { Card, CardHeader } from "../ui/Card";
import { Badge } from "../ui/Badge";

function Bar({ label, value }: { label: string; value: number | null | undefined }) {
  const v = value == null ? null : Math.max(0, Math.min(1, value));
  return (
    <div className="grid grid-cols-[7rem_1fr_2.5rem] items-center gap-3 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        {v != null && <div className="h-full rounded-full bg-primary" style={{ width: `${v * 100}%` }} />}
      </div>
      <span className="text-right tabular-nums">{v == null ? "—" : Math.round(v * 100)}</span>
    </div>
  );
}

/** Why the pipeline picked this moment: the score sheet row, as bars. */
export function ScoreBars({ row, judgeScore }: { row: ScoreRow | null; judgeScore?: number }) {
  return (
    <Card>
      <CardHeader title="Score sheet" subtitle="How the moment was found (before Claude)" />
      <div className="grid gap-2.5 p-4">
        {!row && <p className="text-sm text-muted-foreground">No score sheet for this clip (made by an older pipeline).</p>}
        {row && (
          <>
            <Bar label="Sound + picture" value={row.monitor} />
            <Bar label="Hook line" value={row.hook?.hook_score} />
            <Bar label="Reaction" value={row.hook?.reaction} />
            <Bar label="On-screen action" value={row.visual?.action} />
            <Bar label="Combined" value={row.final} />
          </>
        )}
        {judgeScore != null && <Bar label="Claude (of 10)" value={judgeScore / 10} />}
        {row && (
          <div className="mt-1 flex flex-wrap gap-1.5">
            {row.visual?.best && <Badge tone="info">{row.visual.best}</Badge>}
            {row.hook?.reaction_labels?.map((l) => <Badge key={l}>{l}</Badge>)}
            {row.notes?.map((n) => <Badge key={n} tone="warning">{n}</Badge>)}
          </div>
        )}
      </div>
    </Card>
  );
}
