"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { CheckCircle2, AlertCircle, X } from "lucide-react";
import { cn } from "./cn";

type Toast = { id: number; tone: "ok" | "error"; text: string };
type Api = { ok: (text: string) => void; error: (err: unknown) => void };

const Ctx = createContext<Api | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);

  const push = useCallback((tone: Toast["tone"], text: string) => {
    const id = Date.now() + Math.random();
    setItems((xs) => [...xs.slice(-3), { id, tone, text }]);
    setTimeout(() => setItems((xs) => xs.filter((t) => t.id !== id)), tone === "error" ? 7000 : 3500);
  }, []);

  const api = useMemo<Api>(() => ({
    ok: (text) => push("ok", text),
    error: (err) => push("error", err instanceof Error ? err.message : String(err)),
  }), [push]);

  return (
    <Ctx.Provider value={api}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed right-4 bottom-4 z-50 grid w-80 gap-2">
        {items.map((t) => (
          <div key={t.id} className={cn(
            "animate-rise pointer-events-auto flex items-start gap-2 rounded-xl border bg-popover p-3 text-sm shadow-lg",
            t.tone === "error" && "border-destructive/40",
          )}>
            {t.tone === "ok" ? <CheckCircle2 size={18} className="shrink-0 text-emerald-600" /> : <AlertCircle size={18} className="shrink-0 text-destructive" />}
            <span className="flex-1">{t.text}</span>
            <button aria-label="Dismiss" onClick={() => setItems((xs) => xs.filter((x) => x.id !== t.id))}><X size={14} /></button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useToast(): Api {
  const api = useContext(Ctx);
  if (!api) throw new Error("useToast must be used inside ToastProvider");
  return api;
}
