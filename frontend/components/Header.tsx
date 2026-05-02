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
    <header className="flex items-center justify-between border-b border-[#30363d] border-t-2 border-t-[#ecad0a] bg-[#161b22] px-3 py-2 md:px-4 md:py-2.5">
      <div className="flex items-baseline gap-2">
        <span className="text-lg font-bold tracking-tight text-[#ecad0a]">FinAlly</span>
        <span className="hidden sm:inline text-[10px] uppercase tracking-widest text-[#8b949e]">AI Trading Workstation</span>
      </div>
      <div className="flex items-center gap-3 md:gap-6">
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-widest text-[#8b949e]">Portfolio</div>
          <div className="font-mono text-base font-bold text-[#e6edf3] md:text-lg">{formatINR(totalValue)}</div>
        </div>
        <div className="hidden sm:block text-right">
          <div className="text-[10px] uppercase tracking-widest text-[#8b949e]">Cash</div>
          <div className="font-mono text-sm font-medium text-[#e6edf3] md:text-base">{formatINR(cashBalance)}</div>
        </div>
        <div className="flex items-center gap-1.5 rounded border border-[#30363d] bg-[#0d1117] px-2 py-1.5">
          <span className={`inline-block h-2 w-2 flex-shrink-0 rounded-full ${dotColor[status]}`} aria-label={statusLabel[status]} />
          <span className="hidden sm:inline text-xs text-[#8b949e]">{statusLabel[status]}</span>
        </div>
        <div className="flex items-center gap-2 border-l border-[#30363d] pl-3 md:gap-3 md:pl-4">
          <span className="hidden sm:inline text-xs text-[#8b949e]">
            <span className="font-medium text-[#e6edf3]">{username}</span>
          </span>
          <button
            type="button"
            onClick={onLogout}
            className="rounded border border-[#30363d] px-2 py-1 text-xs text-[#8b949e] transition-colors hover:border-[#ef4444] hover:text-[#ef4444] md:px-2.5"
          >
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}
