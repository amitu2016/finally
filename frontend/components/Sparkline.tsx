"use client";

import { Line, LineChart, ResponsiveContainer, YAxis } from "recharts";

interface Props {
  data: number[];
  positive: boolean;
}

export function Sparkline({ data, positive }: Props) {
  if (!data || data.length < 2) {
    return <div className="h-7 w-20 text-[10px] text-[#30363d]">—</div>;
  }
  const series = data.map((price, idx) => ({ idx, price }));
  const stroke = positive ? "#22c55e" : "#ef4444";
  return (
    <div className="h-7 w-20">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={series} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
          <YAxis hide domain={["dataMin", "dataMax"]} />
          <Line
            type="monotone"
            dataKey="price"
            stroke={stroke}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
