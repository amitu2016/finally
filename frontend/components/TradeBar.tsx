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
    <section className="border-t border-[#30363d] bg-[#161b22] px-3 py-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="hidden sm:inline text-[10px] uppercase tracking-widest text-[#8b949e]">Trade</span>
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          placeholder="TICKER"
          className="min-w-[72px] flex-1 rounded border border-[#30363d] bg-[#0d1117] px-2 py-2 font-mono text-sm text-[#e6edf3] outline-none transition-colors focus:border-[#209dd7] sm:flex-none sm:w-28"
        />
        <input
          type="number"
          min="0"
          step="any"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          placeholder="Qty"
          className="w-20 rounded border border-[#30363d] bg-[#0d1117] px-2 py-2 font-mono text-sm text-[#e6edf3] outline-none transition-colors focus:border-[#209dd7]"
        />
        <button
          type="button"
          disabled={busy}
          onClick={() => void submit("buy")}
          className="flex-1 rounded bg-[#209dd7] px-5 py-2 text-xs font-bold tracking-widest text-[#0d1117] transition-all hover:brightness-110 disabled:opacity-40 sm:flex-none"
        >
          BUY
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void submit("sell")}
          className="flex-1 rounded bg-[#ef4444] px-5 py-2 text-xs font-bold tracking-widest text-white transition-all hover:brightness-110 disabled:opacity-40 sm:flex-none"
        >
          SELL
        </button>
      </div>
      {feedback && (
        <p
          className={`mt-1 text-[11px] ${feedback.kind === "ok" ? "text-[#22c55e]" : "text-[#ef4444]"}`}
          role="status"
        >
          {feedback.text}
        </p>
      )}
    </section>
  );
}
