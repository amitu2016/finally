"use client";

import { useEffect, useRef, useState } from "react";
import {
  AreaSeries,
  ColorType,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { api } from "@/lib/api";
import { formatINR, formatPct, pnlColor } from "@/lib/format";
import type { PriceTick } from "@/lib/types";

interface Props {
  ticker: string | null;
  liveTick: PriceTick | undefined;
}

function toEpoch(ts: string): UTCTimestamp {
  return Math.floor(new Date(ts).getTime() / 1000) as UTCTimestamp;
}

export function MainChart({ ticker, liveTick }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const lastTimeRef = useRef<number>(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0d1117" },
        textColor: "#8b949e",
        fontFamily: "var(--font-geist-mono), monospace",
      },
      grid: {
        vertLines: { color: "#1f2632" },
        horzLines: { color: "#1f2632" },
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: "#30363d" },
      timeScale: { borderColor: "#30363d", timeVisible: true, secondsVisible: false },
      autoSize: true,
    });
    const series = chart.addSeries(AreaSeries, {
      lineColor: "#209dd7",
      topColor: "rgba(32, 157, 215, 0.4)",
      bottomColor: "rgba(32, 157, 215, 0.02)",
      lineWidth: 2,
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
    });
    chartRef.current = chart;
    seriesRef.current = series;
    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!ticker || !seriesRef.current) {
      seriesRef.current?.setData([]);
      lastTimeRef.current = 0;
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .priceHistory(ticker)
      .then((points) => {
        if (cancelled || !seriesRef.current) return;
        const seen = new Set<number>();
        const data = points
          .map((p) => ({ time: toEpoch(p.timestamp), value: p.price }))
          .filter((p) => {
            if (seen.has(p.time)) return false;
            seen.add(p.time);
            return true;
          })
          .sort((a, b) => a.time - b.time);
        seriesRef.current.setData(data);
        lastTimeRef.current = data.length ? data[data.length - 1].time : 0;
        chartRef.current?.timeScale().fitContent();
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [ticker]);

  useEffect(() => {
    if (!ticker || !seriesRef.current || !liveTick || liveTick.ticker !== ticker) return;
    const time = toEpoch(liveTick.timestamp);
    if (time <= lastTimeRef.current) return;
    seriesRef.current.update({ time, value: liveTick.price });
    lastTimeRef.current = time;
  }, [ticker, liveTick]);

  const change = liveTick?.change_pct ?? null;

  return (
    <section className="flex h-full flex-col bg-[#0d1117]">
      <div className="flex items-center justify-between border-b border-[#30363d] bg-[#161b22] px-4 py-2">
        <div>
          <h2 className="font-mono text-sm font-semibold text-[#e6edf3]">
            {ticker ?? "Select a ticker"}
          </h2>
          {liveTick?.company_name && (
            <p className="text-[10px] text-[#8b949e]">{liveTick.company_name}</p>
          )}
        </div>
        <div className="flex items-baseline gap-3">
          <span className="font-mono text-base text-[#e6edf3]">
            {formatINR(liveTick?.price ?? null)}
          </span>
          <span className={`font-mono text-xs ${pnlColor(change)}`}>
            {formatPct(change)}
          </span>
        </div>
      </div>
      <div className="relative flex-1">
        {loading && (
          <div className="absolute right-3 top-3 text-[10px] uppercase tracking-widest text-[#8b949e]">
            Loading…
          </div>
        )}
        {error && (
          <div className="absolute left-3 top-3 text-[10px] text-[#ef4444]" role="alert">
            {error}
          </div>
        )}
        {!ticker && (
          <div className="flex h-full items-center justify-center text-xs text-[#8b949e]">
            Click a ticker on the watchlist to view its chart.
          </div>
        )}
        <div ref={containerRef} className="absolute inset-0" />
      </div>
    </section>
  );
}
