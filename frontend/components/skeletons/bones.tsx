import { cn } from "../ui/cn";

export const times = (n: number) => Array.from({ length: n }, (_, i) => i);

/** A grey block with an explicit size (images, buttons, inputs, circles). */
export function Bone({ className }: { className?: string }) {
  return <span aria-hidden className={cn("block animate-pulse rounded-lg bg-muted", className)} />;
}

/**
 * A line of text. Put it inside the same element and text classes as the real text: the line height
 * then comes from those classes, so the placeholder is exactly as tall as the text it stands for.
 */
export function Line({ className }: { className?: string }) {
  return <span aria-hidden className={cn("inline-block h-[0.75em] max-w-full animate-pulse rounded bg-muted align-baseline", className)} />;
}

/** Same box as EmptyState, for a list that is known to be empty. */
export function EmptySkeleton({ hint = false }: { hint?: boolean }) {
  return (
    <div className="grid place-items-center gap-2 rounded-xl border border-dashed p-10 text-center">
      <Bone className="size-6" />
      <p className="font-semibold"><Line className="w-40" /></p>
      {hint && <div className="text-sm"><Line className="w-64" /></div>}
    </div>
  );
}
