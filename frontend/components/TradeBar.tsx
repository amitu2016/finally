"use client";

import { useEffect, useState } from "react";
import type { Portfolio, TradeRequest } from "@/lib/types";

interface Props {
  initialTicker?: string | null;
  onTrade: (req: TradeRequest) => Promise<Portfolio>;
}

export function TradeBar({ initialTicker, onTrade }: Props) {
  const [ticker, setTicker] = useState(initialTicker ?? "");

  useEffect(() => {
    if (initialTicker) setTicker(initialTicker);
  }, [initialTicker]);

  const [quantity, setQuantity] = useState("1");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{ kind: "ok" | "err"; text: string } | null>(
    null,
  );

  const submit = async (side: "buy" | "sell") => {
    const qty = Number(quantity);
    if (!ticker.trim() || !Number.isFinite(qty) || qty <= 0) {
      setFeedback({ kind: "err", text: "Enter a ticker and a positive quantity." });
      return;
    }
    setBusy(true);
    setFeedback(null);
    try {
      await onTrade({ ticker: ticker.trim().toUpperCase(), quantity: qty, side });
      setFeedback({
        kind: "ok",
        text: `${side === "buy" ? "Bought" : "Sold"} ${qty} ${ticker.toUpperCase()}`,
      });
    } catch (err) {
      setFeedback({
        kind: "err",
        text: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="flex items-center gap-3 border-t border-[#30363d] bg-[#161b22] px-4 py-2">
      <span className="text-[10px] uppercase tracking-widest text-[#8b949e]">Trade</span>
      <input
        value={ticker}
        onChange={(e) => setTicker(e.target.value.toUpperCase())}
        placeholder="TICKER"
        className="w-28 rounded border border-[#30363d] bg-[#0d1117] px-2 py-1 font-mono text-xs text-[#e6edf3] outline-none focus:border-[#209dd7]"
      />
      <input
        type="number"
        min="0"
        step="any"
        value={quantity}
        onChange={(e) => setQuantity(e.target.value)}
        placeholder="Qty"
        className="w-24 rounded border border-[#30363d] bg-[#0d1117] px-2 py-1 font-mono text-xs text-[#e6edf3] outline-none focus:border-[#209dd7]"
      />
      <button
        type="button"
        disabled={busy}
        onClick={() => void submit("buy")}
        className="rounded bg-[#209dd7] px-4 py-1 text-xs font-semibold text-[#0d1117] disabled:opacity-40"
      >
        BUY
      </button>
      <button
        type="button"
        disabled={busy}
        onClick={() => void submit("sell")}
        className="rounded bg-[#ef4444] px-4 py-1 text-xs font-semibold text-[#0d1117] disabled:opacity-40"
      >
        SELL
      </button>
      {feedback && (
        <span
          className={`text-[11px] ${
            feedback.kind === "ok" ? "text-[#22c55e]" : "text-[#ef4444]"
          }`}
          role="status"
        >
          {feedback.text}
        </span>
      )}
    </section>
  );
}
