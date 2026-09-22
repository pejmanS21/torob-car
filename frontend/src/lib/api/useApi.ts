"use client";
import { useCallback, useEffect, useEffectEvent, useState } from "react";
import { ApiError, isAbort } from "./client";

export interface ApiState<T> { data: T | null; error: ApiError | null; loading: boolean; retry(): void; }

type Fetcher<T> = (signal: AbortSignal) => Promise<T>;
interface Settled<T> { key: string; attempt: number; data: T | null; error: ApiError | null; }

function asApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  const message = error instanceof Error ? error.message : "request failed";
  return new ApiError(0, "network_error", message);
}

/**
 * Fetch `key` with `fetcher`; a new key aborts the request in flight, so a superseded
 * response never overwrites a newer one. `key === null` means "nothing to fetch".
 * State is only set from the promise callbacks (never synchronously in the effect).
 */
export function useApi<T>(key: string | null, fetcher: Fetcher<T>): ApiState<T> {
  const [attempt, setAttempt] = useState(0);
  const [settled, setSettled] = useState<Settled<T>>({ key: "", attempt: -1, data: null, error: null });
  const run = useEffectEvent((signal: AbortSignal) => fetcher(signal)); // always the latest fetcher, never a dependency

  useEffect(() => {
    if (key === null) return;
    const controller = new AbortController();
    run(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setSettled({ key, attempt, data, error: null });
      })
      .catch((error: unknown) => {
        if (isAbort(error) || controller.signal.aborted) return;
        setSettled({ key, attempt, data: null, error: asApiError(error) });
      });
    return () => controller.abort();
  }, [key, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  const current = key !== null && settled.key === key && settled.attempt === attempt;
  return {
    data: current ? settled.data : null,
    error: current ? settled.error : null,
    loading: key !== null && !current,
    retry,
  };
}
