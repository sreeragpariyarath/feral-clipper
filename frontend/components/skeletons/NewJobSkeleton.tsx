import { Card } from "../ui/Card";
import { Bone, Line } from "./bones";

function FieldSkeleton({ label }: { label: string }) {
  return (
    <div className="grid content-start gap-1.5 text-sm">
      <span className="font-medium">{label}</span>
      <Bone className="h-[38px] w-full" />
      <span className="text-xs"><Line className="w-52" /></span>
    </div>
  );
}

/** Mirrors NewJobForm. */
export function NewJobSkeleton() {
  return (
    <Card className="p-6">
      <div className="grid gap-5">
        <Bone className="h-[38px] w-72" />
        <FieldSkeleton label="VOD link" />
        <div className="grid gap-4 sm:grid-cols-[1fr_10rem]">
          <FieldSkeleton label="What to do" />
          <FieldSkeleton label="Clips to make" />
        </div>
        <FieldSkeleton label="Campaign" />
        <div className="flex justify-end"><Bone className="h-10 w-24" /></div>
      </div>
    </Card>
  );
}
