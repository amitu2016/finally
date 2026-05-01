"use client";

import { Sparkline } from "./Sparkline";
import { PriceCell } from "./PriceCell";
import { AddTickerForm } from "./AddTickerForm";
import { formatPct, pnlColor } from "@/lib/format";
import type { PriceTick, WatchlistEntry } from "@/lib/types";

interface Props {
  entries: WatchlistEntry[];
  prices: Record<string, PriceTick>;
  sparklines: Record<string, number[]>;
  selected: string | null;
  onSelect: (ticker: string) => void;
  onAdd: (ticker: string) => Promise<void>;
  onRemove: (ticker: string) => Promise<void>;
}

export function WatchlistPanel({
  entries,
  prices,
  sparklines,
  selected,
  onSelect,
  onAdd,
  onRemove,
}: Props) {
  return (
    <section className="flex h-full flex-col border-r border-[#30363d] bg-[#0d1117]">
      <div className="flex items-center justify-between border-b border-[#30363d] bg-[#161b22] px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-[#8b949e]">
          Watchlist
        </h2>
        <span className="text-[10px] text-[#8b949e]">
          {entries.length} symbols
        </span>
      </div>
      <div className="scrollbar-thin flex-1 overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-[#161b22] text-[10px] uppercase tracking-wider text-[#8b949e]">
            <tr>
              <th className="px-2 py-2 text-left">Symbol</th>
              <th className="px-2 py-2 text-right">Price</th>
              <th className="px-2 py-2 text-right">Chg%</th>
              <th className="px-2 py-2 text-right">Trend</th>
              <th className="px-1 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => {
              const tick = prices[entry.ticker];
              const livePrice = tick?.price ?? entry.price;
              const change = tick?.change_pct ?? entry.change_pct;
              const positive = (change ?? 0) >= 0;
              const isSelected = selected === entry.ticker;
              return (
                <tr
                  key={entry.ticker}
                  onClick={() => onSelect(entry.ticker)}
                  className={`cursor-pointer border-b border-[#21262d] hover:bg-[#161b22] ${
                    isSelected ? "bg-[#1f2632]" : ""
                  }`}
                >
                  <td className="px-2 py-2">
                    <div className="font-mono font-semibold text-[#e6edf3]">
                      {entry.ticker}
                    </div>
                    {(tick?.company_name || entry.company_name) && (
                      <div className="truncate text-[10px] text-[#8b949e]">
                        {tick?.company_name ?? entry.company_name}
                      </div>
                    )}
                  </td>
                  <td className="px-2 py-2 text-right text-[#e6edf3]">
                    <PriceCell price={livePrice ?? null} />
                  </td>
                  <td className={`px-2 py-2 text-right font-mono ${pnlColor(change)}`}>
                    {formatPct(change)}
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex justify-end">
                      <Sparkline
                        data={sparklines[entry.ticker] ?? []}
                        positive={positive}
                      />
                    </div>
                  </td>
                  <td className="px-2 py-2 text-right">
                    <button
                      type="button"
                      aria-label={`Remove ${entry.ticker}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        void onRemove(entry.ticker);
                      }}
                      className="rounded p-1 text-[#ef4444] hover:bg-[#30363d]"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                        <path d="M10 11v6M14 11v6" />
                        <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
                      </svg>
                    </button>
                  </td>
                </tr>
              );
            })}
            {entries.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-[#8b949e]">
                  No tickers — add one below.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <AddTickerForm onAdd={onAdd} />
    </section>
  );
}
