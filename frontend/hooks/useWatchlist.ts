"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { WatchlistEntry } from "@/lib/types";

export interface WatchlistState {
  entries: WatchlistEntry[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  addTicker: (ticker: string) => Promise<void>;
  removeTicker: (ticker: string) => Promise<void>;
}

export function useWatchlist(): WatchlistState {
  const [entries, setEntries] = useState<WatchlistEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await api.getWatchlist();
      setEntries(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const addTicker = useCallback(
    async (ticker: string) => {
      const cleaned = ticker.trim().toUpperCase();
      if (!cleaned) return;
      const updated = await api.addWatchlist(cleaned);
      setEntries(updated);
    },
    [],
  );

  const removeTicker = useCallback(async (ticker: string) => {
    const updated = await api.removeWatchlist(ticker);
    setEntries(updated);
  }, []);

  return { entries, loading, error, refresh, addTicker, removeTicker };
}
