"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PortfolioSnapshot } from "@/lib/types";
import { formatINR } from "@/lib/format";

interface Props {
  history: PortfolioSnapshot[];
}

export function PnLChart({ history }: Props) {
  const data = history.map((h) => ({
    t: new Date(h.recorded_at).getTime(),
    label: new Date(h.recorded_at).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    }),
    value: h.total_value,
  }));

  return (
    <section className="flex h-full flex-col border-l border-[#30363d] bg-[#0d1117]">
      <div className="border-b border-[#30363d] bg-[#161b22] px-3 py-2">
        <h2 className="section-header text-xs font-semibold uppercase tracking-widest text-[#8b949e]">
          Portfolio Value
        </h2>
      </div>
      <div className="flex-1 px-2 py-2">
        {data.length < 2 ? (
          <div className="flex h-full items-center justify-center text-xs text-[#8b949e]">
            Awaiting snapshots…
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
              <CartesianGrid stroke="#1f2632" strokeDasharray="3 3" />
              <XAxis
                dataKey="label"
                stroke="#8b949e"
                fontSize={10}
                tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                stroke="#8b949e"
                fontSize={10}
                tickLine={false}
                width={70}
                domain={["auto", "auto"]}
                tickFormatter={(v: number) => formatINR(v)}
              />
              <Tooltip
                contentStyle={{
                  background: "#161b22",
                  border: "1px solid #30363d",
                  fontSize: 12,
                  color: "#e6edf3",
                }}
                formatter={(value) => formatINR(Number(value))}
                labelStyle={{ color: "#8b949e" }}
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#209dd7"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}
