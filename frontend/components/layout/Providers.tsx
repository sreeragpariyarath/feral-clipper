"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { ApiError } from "@/lib/api";
import { ToastProvider } from "../ui/Toast";

// A 4xx answer won't change on retry; only network or server errors are worth one more try.
const retry = (count: number, err: unknown) => !(err instanceof ApiError && err.status < 500) && count < 1;

export function Providers({ children }: { children: ReactNode }) {
  // Live events keep data fresh, so queries don't refetch on a timer.
  const [client] = useState(() => new QueryClient({
    defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: true, retry } },
  }));
  return (
    <QueryClientProvider client={client}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );
}
