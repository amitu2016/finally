"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Portfolio, PortfolioSnapshot, TradeRequest } from "@/lib/types";

export interface PortfolioState {
  portfolio: Portfolio | null;
  history: PortfolioSnapshot[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  executeTrade: (req: TradeRequest) => Promise<Portfolio>;
}

export function usePortfolio(): PortfolioState {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [history, setHistory] = useState<PortfolioSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [p, h] = await Promise.all([api.getPortfolio(), api.getPortfolioHistory()]);
      setPortfolio(p);
      setHistory(h);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const interval = setInterval(() => {
      void refresh();
    }, 15000);
    return () => clearInterval(interval);
  }, [refresh]);

  const executeTrade = useCallback(
    async (req: TradeRequest) => {
      const updated = await api.trade(req);
      setPortfolio(updated);
      void refresh();
      return updated;
    },
    [refresh],
  );

  return { portfolio, history, loading, error, refresh, executeTrade };
}
