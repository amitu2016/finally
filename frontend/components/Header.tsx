"use client";

import type { ConnectionStatus } from "@/lib/types";
import { formatINR } from "@/lib/format";

interface Props {
  totalValue: number | null;
  cashBalance: number | null;
  status: ConnectionStatus;
  username: string;
  onLogout: () => void;
}

const dotColor: Record<ConnectionStatus, string> = {
  connected: "bg-[#22c55e] shadow-[0_0_8px_#22c55e]",
  connecting: "bg-[#ecad0a] shadow-[0_0_8px_#ecad0a]",
  disconnected: "bg-[#ef4444] shadow-[0_0_8px_#ef4444]",
};

const statusLabel: Record<ConnectionStatus, string> = {
  connected: "Live",
  connecting: "Connecting",
  disconnected: "Disconnected",
};

export function Header({ totalValue, cashBalance, status, username, onLogout }: Props) {
  return (
    <header className="flex items-center justify-between border-b border-[#30363d] bg-[#161b22] px-4 py-3">
      <div className="flex items-baseline gap-2">
        <span className="text-lg font-bold tracking-tight text-[#ecad0a]">FinAlly</span>
        <span className="text-xs uppercase tracking-widest text-[#8b949e]">AI Trading Workstation</span>
      </div>
      <div className="flex items-center gap-6">
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-widest text-[#8b949e]">Total Value</div>
          <div className="font-mono text-base font-semibold text-[#e6edf3]">{formatINR(totalValue)}</div>
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-widest text-[#8b949e]">Cash</div>
          <div className="font-mono text-base text-[#e6edf3]">{formatINR(cashBalance)}</div>
        </div>
        <div className="flex items-center gap-2 rounded border border-[#30363d] bg-[#0d1117] px-3 py-1.5">
          <span className={`inline-block h-2 w-2 rounded-full ${dotColor[status]}`} aria-label={statusLabel[status]} />
          <span className="text-xs text-[#8b949e]">{statusLabel[status]}</span>
        </div>
        <div className="flex items-center gap-3 border-l border-[#30363d] pl-4">
          <span className="text-xs text-[#8b949e]">
            <span className="text-[#e6edf3] font-medium">{username}</span>
          </span>
          <button
            type="button"
            onClick={onLogout}
            className="rounded border border-[#30363d] px-2.5 py-1 text-xs text-[#8b949e] hover:border-[#ef4444] hover:text-[#ef4444] transition-colors"
          >
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}
