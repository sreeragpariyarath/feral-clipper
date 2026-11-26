import { Card, CardHeader } from "../ui/Card";
import { PageHeader } from "../ui/PageHeader";
import { Bone, Line, times } from "./bones";

const FACTS = ["Kind", "Clips asked for", "Created", "Run time", "Claude tokens", "Stream"];

/** Mirrors the job page: back link, header, step timeline, facts and log bar. */
export function JobDetailSkeleton() {
  return (
    <>
      <div className="mb-3 text-sm"><Line className="w-14" /></div>
      <PageHeader title={<Line className="w-72" />} subtitle={<Line className="w-96" />} actions={<Bone className="h-10 w-36" />} />
      <div className="grid gap-4 lg:grid-cols-[1fr_16rem]">
        <Card>
          <CardHeader title="Steps" subtitle={<Line className="w-24" />} />
          <ol className="grid p-4">
            {times(12).map((i) => (
              <li key={i} className="flex gap-3 pb-5 last:pb-0">
                <Bone className="size-7 shrink-0 rounded-full" />
                <div className="min-w-0 flex-1 pt-0.5">
                  <p className="font-medium"><Line className="w-56" /></p>
                  <p className="text-xs"><Line className="w-40" /></p>
                </div>
              </li>
            ))}
          </ol>
        </Card>
        <Card className="h-fit p-4">
          <dl className="grid gap-3">
            {FACTS.map((f) => (
              <div key={f}>
                <dt className="text-xs text-muted-foreground">{f}</dt>
                <dd className="text-sm"><Line className="w-32" /></dd>
              </div>
            ))}
          </dl>
        </Card>
      </div>
      <Bone className="mt-4 h-[46px] w-full rounded-xl" />
    </>
  );
}
