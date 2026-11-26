import { Card, CardHeader } from "../ui/Card";
import { PageHeader } from "../ui/PageHeader";
import { Bone, Line, times } from "./bones";

/** Mirrors the PostingKit card. */
export function PostingKitSkeleton() {
  return (
    <Card>
      <CardHeader title="Posting kit" subtitle={<Line className="w-40" />} />
      <div className="grid gap-4 p-4">
        <Bone className="h-[38px] w-64" />
        <div className="grid gap-1"><span className="text-sm"><Line className="w-12" /></span><Bone className="h-9 w-full" /></div>
        <div className="grid gap-1"><span className="text-sm"><Line className="w-20" /></span><Bone className="h-48 w-full" /></div>
        <Bone className="h-24 w-full" />
        <div className="flex gap-2 border-t pt-4"><Bone className="h-[38px] flex-1" /><Bone className="h-10 w-36" /></div>
      </div>
    </Card>
  );
}

/** Mirrors the clip page: back link, header with actions, video on the left, cards on the right. */
export function ClipDetailSkeleton() {
  return (
    <>
      <div className="mb-3 text-sm"><Line className="w-14" /></div>
      <PageHeader title={<Line className="w-96" />} subtitle={<Line className="w-72" />}
        actions={<><Bone className="h-10 w-28" /><Bone className="h-10 w-24" /><Bone className="h-10 w-32" /><Bone className="size-9" /></>} />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,22rem)_1fr]">
        <div><Card className="overflow-hidden"><div className="aspect-[9/16] w-full animate-pulse bg-muted" /></Card></div>
        <div className="grid content-start gap-5">
          <Card>
            <CardHeader title="Post text" action={<Bone className="h-8 w-20" />} />
            <div className="grid gap-4 p-4">
              <div className="grid gap-1.5 text-sm">
                <span className="font-medium">Title</span>
                <div className="flex gap-2"><Bone className="h-[38px] flex-1" /><Bone className="size-9" /></div>
                <span className="text-xs"><Line className="w-52" /></span>
              </div>
              <div className="grid gap-1.5 text-sm">
                <span className="font-medium">Caption and hashtags</span>
                <div className="flex gap-2"><Bone className="h-24 flex-1" /><Bone className="size-9" /></div>
              </div>
            </div>
          </Card>
          <PostingKitSkeleton />
          {["Judge notes", "Transcript", "Score sheet"].map((title) => (
            <Card key={title}>
              <CardHeader title={title} subtitle={<Line className="w-40" />} />
              <div className="grid gap-2.5 p-4 text-sm">
                {times(4).map((i) => <div key={i}><Line className={i === 3 ? "w-1/2" : "w-full"} /></div>)}
              </div>
            </Card>
          ))}
        </div>
      </div>
    </>
  );
}
