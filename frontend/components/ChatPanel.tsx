"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";
import { formatINR } from "@/lib/format";

interface Props {
  open: boolean;
  onToggle: () => void;
  onActions: () => void;
}

function makeId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

export function ChatPanel({ open, onToggle, onActions }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages, busy]);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    const userMsg: ChatMessage = { id: makeId(), role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setBusy(true);
    try {
      const res = await api.chat(text);
      const reply: ChatMessage = {
        id: makeId(),
        role: "assistant",
        content: res.message,
        trades_executed: res.trades_executed,
        watchlist_changes: res.watchlist_changes,
        errors: res.errors,
      };
      setMessages((prev) => [...prev, reply]);
      if (
        (res.trades_executed && res.trades_executed.length > 0) ||
        (res.watchlist_changes && res.watchlist_changes.length > 0)
      ) {
        onActions();
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: makeId(),
          role: "assistant",
          content: err instanceof Error ? err.message : String(err),
          errors: [err instanceof Error ? err.message : String(err)],
        },
      ]);
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={onToggle}
        className="flex h-full w-10 flex-col items-center justify-center border-l border-[#30363d] bg-[#161b22] text-[10px] uppercase tracking-widest text-[#8b949e] hover:text-[#ecad0a]"
        aria-label="Open AI chat"
      >
        <span className="rotate-180" style={{ writingMode: "vertical-rl" }}>
          AI Assistant
        </span>
      </button>
    );
  }

  return (
    <section className="flex h-full w-full flex-col border-l border-[#30363d] bg-[#0d1117] md:w-80">
      <div className="flex items-center justify-between border-b border-[#30363d] bg-[#161b22] px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-[#ecad0a]">
          AI Copilot
        </h2>
        <button
          type="button"
          onClick={onToggle}
          aria-label="Collapse chat"
          className="rounded px-2 text-[#8b949e] hover:bg-[#30363d]"
        >
          ›
        </button>
      </div>
      <div ref={listRef} className="scrollbar-thin flex-1 space-y-3 overflow-y-auto px-3 py-3">
        {messages.length === 0 && (
          <p className="text-xs text-[#8b949e]">
            Ask FinAlly about your portfolio, request analysis, or have it execute trades.
          </p>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 text-xs leading-relaxed ${
                msg.role === "user"
                  ? "bg-[#209dd7] text-[#0d1117]"
                  : "bg-[#161b22] text-[#e6edf3] border border-[#30363d]"
              }`}
            >
              <div className="whitespace-pre-wrap">{msg.content}</div>
              {msg.trades_executed && msg.trades_executed.length > 0 && (
                <div className="mt-2 space-y-0.5 border-t border-[#30363d] pt-2 text-[11px] text-[#22c55e]">
                  {msg.trades_executed.map((t, i) => (
                    <div key={i} className="font-mono">
                      {t.side === "buy" ? "Bought" : "Sold"} {t.quantity} {t.ticker}
                      {t.price !== undefined && ` @ ${formatINR(t.price)}`}
                    </div>
                  ))}
                </div>
              )}
              {msg.watchlist_changes && msg.watchlist_changes.length > 0 && (
                <div className="mt-2 space-y-0.5 border-t border-[#30363d] pt-2 text-[11px] text-[#ecad0a]">
                  {msg.watchlist_changes.map((w, i) => (
                    <div key={i} className="font-mono">
                      Watchlist {w.action === "add" ? "+" : "-"} {w.ticker}
                    </div>
                  ))}
                </div>
              )}
              {msg.errors && msg.errors.length > 0 && (
                <div className="mt-2 space-y-0.5 border-t border-[#30363d] pt-2 text-[11px] text-[#ef4444]">
                  {msg.errors.map((e, i) => (
                    <div key={i}>{e}</div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex justify-start">
            <div className="rounded-lg border border-[#30363d] bg-[#161b22] px-3 py-2 text-xs text-[#8b949e]">
              FinAlly is thinking…
            </div>
          </div>
        )}
      </div>
      <div className="flex gap-2 border-t border-[#30363d] bg-[#161b22] p-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
          placeholder="Ask the AI…"
          disabled={busy}
          className="flex-1 rounded border border-[#30363d] bg-[#0d1117] px-2 py-1 text-xs text-[#e6edf3] outline-none focus:border-[#753991] disabled:opacity-50"
        />
        <button
          type="button"
          disabled={busy || !input.trim()}
          onClick={() => void send()}
          className="rounded bg-[#753991] px-3 py-1 text-xs font-semibold text-white disabled:opacity-40"
        >
          Send
        </button>
      </div>
    </section>
  );
}
