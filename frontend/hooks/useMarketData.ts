"use client";

import { useEffect, useRef, useState } from "react";
import type { ConnectionStatus, PriceTick } from "@/lib/types";

const SPARK_LIMIT = 60;

export interface MarketDataState {
  prices: Record<string, PriceTick>;
  sparklines: Record<string, number[]>;
  status: ConnectionStatus;
  lastTick: PriceTick | null;
}

export function useMarketData(): MarketDataState {
  const [prices, setPrices] = useState<Record<string, PriceTick>>({});
  const [sparklines, setSparklines] = useState<Record<string, number[]>>({});
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [lastTick, setLastTick] = useState<PriceTick | null>(null);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource("/api/stream/prices");
    sourceRef.current = es;
    setStatus("connecting");

    es.onopen = () => setStatus("connected");
    es.onerror = () => {
      setStatus((current) =>
        es.readyState === EventSource.CLOSED ? "disconnected" : "connecting",
      );
    };
    es.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data) as PriceTick | PriceTick[];
        const ticks = Array.isArray(data) ? data : [data];
        if (ticks.length === 0) return;
        setPrices((prev) => {
          const next = { ...prev };
          for (const tick of ticks) next[tick.ticker] = tick;
          return next;
        });
        setSparklines((prev) => {
          const next = { ...prev };
          for (const tick of ticks) {
            const arr = next[tick.ticker] ? [...next[tick.ticker]] : [];
            arr.push(tick.price);
            if (arr.length > SPARK_LIMIT) arr.shift();
            next[tick.ticker] = arr;
          }
          return next;
        });
        setLastTick(ticks[ticks.length - 1]);
      } catch {
        // Ignore malformed events; the stream may emit keepalives.
      }
    };

    return () => {
      es.close();
      sourceRef.current = null;
    };
  }, []);

  return { prices, sparklines, status, lastTick };
}
