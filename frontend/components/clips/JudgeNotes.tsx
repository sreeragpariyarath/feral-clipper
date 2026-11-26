import type { ClipDetail } from "@/lib/types";
import { Badge } from "../ui/Badge";
import { Card, CardHeader } from "../ui/Card";

export function JudgeNotes({ judge }: { judge: ClipDetail["judge"] }) {
  return (
    <Card>
      <CardHeader title="Judge notes" subtitle={judge.source ? `by ${judge.source}` : undefined}
        action={judge.score != null && <Badge tone="brand">{judge.score} / 10</Badge>} />
      <div className="grid gap-3 p-4 text-sm">
        {judge.hook_text && <blockquote className="border-l-4 border-primary pl-3 font-medium italic">“{judge.hook_text}”</blockquote>}
        {judge.reasons && <p className="leading-relaxed text-muted-foreground">{judge.reasons}</p>}
        <div className="flex flex-wrap gap-1.5">
          {judge.category && <Badge tone="info">{judge.category}</Badge>}
          {judge.needs_context && <Badge tone="warning">needs context</Badge>}
          {judge.violations?.map((v) => <Badge key={v} tone="danger">{v}</Badge>)}
        </div>
        {!judge.reasons && !judge.hook_text && <p className="text-muted-foreground">No judge notes.</p>}
      </div>
    </Card>
  );
}
