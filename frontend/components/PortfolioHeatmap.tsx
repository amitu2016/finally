"use client";

import { ResponsiveContainer, Tooltip, Treemap } from "recharts";
import type { Position } from "@/lib/types";
import { formatPct } from "@/lib/format";

interface Props {
  positions: Position[];
}

interface Cell {
  ticker: string;
  pnl_pct: number;
  size: number;
  fill: string;
  [key: string]: string | number;
}

function colorFor(pnlPct: number): string {
  const clamped = Math.max(-10, Math.min(10, pnlPct)) / 10;
  if (clamped >= 0) {
    const intensity = 0.35 + clamped * 0.5;
    return `rgba(34, 197, 94, ${intensity.toFixed(2)})`;
  }
  const intensity = 0.35 + Math.abs(clamped) * 0.5;
  return `rgba(239, 68, 68, ${intensity.toFixed(2)})`;
}

interface ContentProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  ticker?: string;
  pnl_pct?: number;
  fill?: string;
}

function Content(props: ContentProps) {
  const { x = 0, y = 0, width = 0, height = 0, ticker, pnl_pct, fill } = props;
  const showLabel = width > 50 && height > 30;
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        style={{ fill: fill ?? "#21262d", stroke: "#0d1117", strokeWidth: 2 }}
      />
      {showLabel && ticker && (
        <>
          <text
            x={x + width / 2}
            y={y + height / 2 - 4}
            textAnchor="middle"
            fill="#fff"
            fontSize={12}
            fontWeight={600}
            fontFamily="var(--font-geist-mono)"
          >
            {ticker}
          </text>
          <text
            x={x + width / 2}
            y={y + height / 2 + 12}
            textAnchor="middle"
            fill="#fff"
            fontSize={10}
            fontFamily="var(--font-geist-mono)"
          >
            {formatPct(pnl_pct ?? 0)}
          </text>
        </>
      )}
    </g>
  );
}

export function PortfolioHeatmap({ positions }: Props) {
  const data: Cell[] = positions
    .map((p) => ({
      ticker: p.ticker,
      pnl_pct: p.pnl_pct,
      size: Math.max(1, p.quantity * p.current_price),
      fill: colorFor(p.pnl_pct),
    }))
    .filter((c) => c.size > 0);

  return (
    <section className="flex h-full flex-col border-l border-[#30363d] bg-[#0d1117]">
      <div className="border-b border-[#30363d] bg-[#161b22] px-3 py-2">
        <h2 className="section-header text-xs font-semibold uppercase tracking-widest text-[#8b949e]">
          Portfolio Heatmap
        </h2>
      </div>
      <div className="flex-1">
        {data.length === 0 ? (
          <div className="flex h-full items-center justify-center text-xs text-[#8b949e]">
            No open positions yet.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <Treemap
              data={data}
              dataKey="size"
              isAnimationActive={false}
              content={<Content />}
            >
              <Tooltip
                contentStyle={{
                  background: "#161b22",
                  border: "1px solid #30363d",
                  fontSize: 12,
                  color: "#e6edf3",
                }}
                formatter={(_value, _name, item) => {
                  const payload = (item as { payload?: Cell }).payload;
                  return [formatPct(payload?.pnl_pct ?? 0), payload?.ticker ?? ""];
                }}
              />
            </Treemap>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}
