export function formatINR(value: number | null): string {
  if (value === null || value === undefined) return "—";
  return (
    "₹" +
    value.toLocaleString("en-IN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  );
}

export function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function formatNumber(value: number): string {
  return value.toLocaleString("en-IN");
}

export function pnlColor(value: number | null | undefined): string {
  if (value === null || value === undefined || value === 0)
    return "text-[#8b949e]";
  return value > 0 ? "text-[#22c55e]" : "text-[#ef4444]";
}
