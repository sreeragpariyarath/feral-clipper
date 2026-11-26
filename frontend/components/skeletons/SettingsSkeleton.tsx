import { Card, CardHeader } from "../ui/Card";
import { Bone, Line, times } from "./bones";

/** Label on the left, value on the right: the rows inside the settings cards. */
export function SettingRowsSkeleton({ rows, className = "grid gap-3 p-4 text-sm" }: { rows: number; className?: string }) {
  return (
    <div className={className}>
      {times(rows).map((i) => (
        // the spans give each row the text's line height (a bare Line in a flex row would collapse)
        <div key={i} className="flex justify-between gap-3"><span><Line className="w-40" /></span><span><Line className="w-20" /></span></div>
      ))}
    </div>
  );
}

/** Mirrors the Settings page cards. */
export function SettingsSkeleton() {
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card>
        <CardHeader title="API keys" subtitle="Edit .env, then restart the API window" />
        <SettingRowsSkeleton rows={2} />
      </Card>
      <Card>
        <CardHeader title="This PC" />
        <SettingRowsSkeleton rows={3} />
      </Card>
      <Card>
        <CardHeader title="Database backup" subtitle="Reviews, campaigns and posts; saved in the backups folder"
          action={<Bone className="h-8 w-32" />} />
        <SettingRowsSkeleton rows={1} className="grid gap-1.5 p-4 text-sm" />
      </Card>
    </div>
  );
}
