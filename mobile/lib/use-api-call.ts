// File: mobile/lib/use-api-call.ts
// Purpose: Hook that wraps apiClient calls with automatic 401 session-refresh
// Usage:   const { data, loading, error, reload } = useApiCall(() => apiClient.get('/api/...'))

import { useCallback, useEffect, useRef, useState } from "react";
import { supabase } from "./supabase";
import { ApiError } from "./api-client";

interface UseApiCallResult<T> {
  data:      T | null;
  loading:   boolean;
  refreshing: boolean;
  error:     string | null;
  reload:    () => void;
  refresh:   () => void; // pull-to-refresh (sets refreshing=true instead of loading)
}

export function useApiCall<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
): UseApiCallResult<T> {
  const [data,       setData]       = useState<T | null>(null);
  const [loading,    setLoading]    = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error,      setError]      = useState<string | null>(null);
  const retried = useRef(false);

  const run = useCallback(async (silent: boolean) => {
    if (!silent) setLoading(true);
    setError(null);
    retried.current = false;

    try {
      const result = await fetcher();
      setData(result);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401 && !retried.current) {
        // Token rejected by the backend — force a session refresh and retry once
        retried.current = true;
        const { error: refreshErr } = await supabase.auth.refreshSession();
        if (!refreshErr) {
          try {
            const result = await fetcher();
            setData(result);
            return;
          } catch (e2) {
            setError(e2 instanceof ApiError ? e2.message : "Request failed");
          }
        } else {
          // Refresh also failed → sign out so the user is taken to login
          await supabase.auth.signOut();
          return;
        }
      } else {
        setError(
          e instanceof ApiError
            ? e.message
            : "Could not connect. Check your internet and try again.",
        );
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => { run(false); }, [run]);

  return {
    data,
    loading,
    refreshing,
    error,
    reload:   () => run(false),
    refresh:  () => { setRefreshing(true); run(true); },
  };
}
