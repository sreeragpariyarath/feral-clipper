import { cn } from "./cn";

/** Progress bar. `value` is 0–100; null shows an indeterminate shimmer. */
export function Progress({ value, className }: { value: number | null | undefined; className?: string }) {
  const known = value != null;
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={known ? Math.round(value) : undefined}
      className={cn("relative h-2 overflow-hidden rounded-full bg-muted", className)}
    >
      <div
        className={cn("relative h-full rounded-full bg-primary transition-[width] duration-500", !known && "progress-sheen w-1/3")}
        style={known ? { width: `${Math.min(100, Math.max(0, value))}%` } : undefined}
      />
    </div>
  );
}
