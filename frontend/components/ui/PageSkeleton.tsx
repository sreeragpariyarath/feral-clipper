import { Skeleton } from "./States";

const times = (n: number) => Array.from({ length: n }, (_, i) => i);

export const TilesSkeleton = ({ count = 4 }: { count?: number }) => (
  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{times(count).map((i) => <Skeleton key={i} className="h-24" />)}</div>
);

export const ClipGridSkeleton = ({ count = 8 }: { count?: number }) => (
  <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">{times(count).map((i) => <Skeleton key={i} className="aspect-[9/16]" />)}</div>
);

export const ListSkeleton = ({ count = 4 }: { count?: number }) => (
  <div className="grid gap-2">{times(count).map((i) => <Skeleton key={i} className="h-20" />)}</div>
);

function Body({ path }: { path: string }) {
  if (path === "/") return <div className="grid gap-6"><TilesSkeleton /><ClipGridSkeleton count={4} /></div>;
  if (path === "/clips") return <div className="grid gap-5"><Skeleton className="h-10 w-96 max-w-full" /><ClipGridSkeleton /></div>;
  if (path.startsWith("/clips/")) {
    return (
      <div className="grid gap-5 lg:grid-cols-[minmax(0,22rem)_1fr]">
        <Skeleton className="aspect-[9/16]" />
        <div className="grid content-start gap-5"><Skeleton className="h-48" /><Skeleton className="h-64" /></div>
      </div>
    );
  }
  if (path.startsWith("/jobs/")) return <div className="grid gap-4 lg:grid-cols-[1fr_16rem]"><Skeleton className="h-96" /><Skeleton className="h-56" /></div>;
  if (path === "/new") return <Skeleton className="h-96 max-w-2xl" />;
  if (path === "/streams") return <Skeleton className="h-64" />;
  if (path === "/settings") return <div className="grid gap-5 lg:grid-cols-2">{times(3).map((i) => <Skeleton key={i} className="h-44" />)}</div>;
  if (path === "/posted") return <div className="grid gap-5"><TilesSkeleton count={3} /><ListSkeleton /></div>;
  return <ListSkeleton />;                                    // jobs, campaigns, trash
}

/** Placeholder shaped like the page that is being opened. */
export function PageSkeleton({ path }: { path: string }) {
  return (
    <div role="status" aria-label="Loading page">
      <div className="mb-6 grid gap-2">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-80 max-w-full" />
      </div>
      <Body path={path} />
    </div>
  );
}
