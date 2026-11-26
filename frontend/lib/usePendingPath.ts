"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

const GIVE_UP_MS = 30_000;

/** The path of an internal link this click will open, or null when the click stays on this page. */
function targetPath(e: MouseEvent): string | null {
  if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return null;
  const a = (e.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
  if (!a || a.hasAttribute("download") || (a.target && a.target !== "_self")) return null;
  const url = new URL(a.href, location.href);
  if (url.origin !== location.origin || /^\/(media|api)\//.test(url.pathname)) return null;
  return url.pathname;
}

/**
 * The page being opened, from the moment a link is clicked until it is on screen; null otherwise.
 * Next only shows the new page once its code has arrived (slow the first time in `pnpm dev`), so this
 * lets the app show a skeleton at once instead of looking frozen.
 */
export function usePendingPath(): string | null {
  const pathname = usePathname();
  const [pending, setPending] = useState<{ to: string; from: string } | null>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      const to = targetPath(e);
      if (to === null) return;
      setPending(to === location.pathname ? null : { to, from: location.pathname });
    };
    const clear = () => setPending(null);                       // browser back / forward
    document.addEventListener("click", onClick, true);          // capture: before <Link> cancels the click
    window.addEventListener("popstate", clear);
    return () => {
      document.removeEventListener("click", onClick, true);
      window.removeEventListener("popstate", clear);
    };
  }, []);

  useEffect(() => {
    if (!pending) return;
    const timer = setTimeout(() => setPending(null), GIVE_UP_MS);  // a failed navigation must not stick
    return () => clearTimeout(timer);
  }, [pending]);

  useEffect(() => setPending(null), [pathname]);

  return pending && pending.from === pathname ? pending.to : null;
}
