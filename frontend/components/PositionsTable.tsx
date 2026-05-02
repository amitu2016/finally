"use client";

import type { Position, PriceTick } from "@/lib/types";
import { formatINR, formatNumber, formatPct, pnlColor } from "@/lib/format";

interface Props {
  positions: Position[];
  prices: Record<string, PriceTick>;
  onSelect: (ticker: string) => void;
}

export function PositionsTable({ positions, prices, onSelect }: Props) {
  return (
    <section className="flex h-full flex-col bg-[#0d1117]">
      <div className="border-b border-[#30363d] bg-[#161b22] px-3 py-2">
        <h2 className="section-header text-xs font-semibold uppercase tracking-widest text-[#8b949e]">
          Positions
        </h2>
      </div>
      <div className="scrollbar-thin flex-1 overflow-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-[#161b22] text-[10px] uppercase tracking-wider text-[#8b949e]">
            <tr>
              <th className="px-3 py-2 text-left">Ticker</th>
              <th className="px-3 py-2 text-right">Qty</th>
              <th className="hidden sm:table-cell px-3 py-2 text-right">Avg Cost</th>
              <th className="hidden sm:table-cell px-3 py-2 text-right">Current</th>
              <th className="px-3 py-2 text-right">Unrealized P&amp;L</th>
              <th className="px-3 py-2 text-right">% Change</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => {
              const live = prices[p.ticker]?.price ?? p.current_price;
              const pnl = (live - p.avg_cost) * p.quantity;
              const pnlPct = p.avg_cost > 0 ? ((live - p.avg_cost) / p.avg_cost) * 100 : 0;
              return (
                <tr
                  key={p.ticker}
                  onClick={() => onSelect(p.ticker)}
                  className="cursor-pointer border-b border-[#21262d] hover:bg-[#161b22]"
                >
                  <td className="px-3 py-2 font-mono font-semibold text-[#e6edf3]">
                    {p.ticker}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-[#e6edf3]">
                    {formatNumber(p.quantity)}
                  </td>
                  <td className="hidden sm:table-cell px-3 py-2 text-right font-mono text-[#e6edf3]">
                    {formatINR(p.avg_cost)}
                  </td>
                  <td className="hidden sm:table-cell px-3 py-2 text-right font-mono text-[#e6edf3]">
                    {formatINR(live)}
                  </td>
                  <td className={`px-3 py-2 text-right font-mono ${pnlColor(pnl)}`}>
                    {formatINR(pnl)}
                  </td>
                  <td className={`px-3 py-2 text-right font-mono ${pnlColor(pnlPct)}`}>
                    {formatPct(pnlPct)}
                  </td>
                </tr>
              );
            })}
            {positions.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-[#8b949e]">
                  No open positions. Place a trade to begin.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
