"use client";

import React, { useCallback, useEffect, useState } from "react";
import { AuthGate } from "@/components/AuthGate";
import { ChatPanel } from "@/components/ChatPanel";
import { Header } from "@/components/Header";
import { MainChart } from "@/components/MainChart";
import { PnLChart } from "@/components/PnLChart";
import { PortfolioHeatmap } from "@/components/PortfolioHeatmap";
import { PositionsTable } from "@/components/PositionsTable";
import { TradeBar } from "@/components/TradeBar";
import { WatchlistPanel } from "@/components/WatchlistPanel";
import { useMarketData } from "@/hooks/useMarketData";
import { usePortfolio } from "@/hooks/usePortfolio";
import { useWatchlist } from "@/hooks/useWatchlist";
import type { AuthUser } from "@/lib/auth";

type MobileTab = "watchlist" | "chart" | "portfolio" | "chat";

function WatchlistIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
      <line x1="3" y1="5" x2="17" y2="5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="3" y1="10" x2="17" y2="10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="3" y1="15" x2="17" y2="15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function ChartIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
      <polyline points="2,15 6,8 11,11 18,4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function PortfolioIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
      <rect x="2" y="2" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="11" y="2" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="2" y="11" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="11" y="11" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function ChatIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path d="M3 4a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H8l-4 3v-3H4a1 1 0 0 1-1-1V4z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

const TABS: { id: MobileTab; label: string; Icon: () => React.JSX.Element }[] = [
  { id: "watchlist", label: "Watch", Icon: WatchlistIcon },
  { id: "chart", label: "Chart", Icon: ChartIcon },
  { id: "portfolio", label: "Portfolio", Icon: PortfolioIcon },
  { id: "chat", label: "AI", Icon: ChatIcon },
];

function TradingApp({ user, onLogout }: { user: AuthUser; onLogout: () => void }) {
  const market = useMarketData();
  const portfolio = usePortfolio();
  const watchlist = useWatchlist();
  const [selected, setSelected] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(true);
  const [activeTab, setActiveTab] = useState<MobileTab>("chart");

  useEffect(() => {
    if (!selected && watchlist.entries.length > 0) {
      setSelected(watchlist.entries[0].ticker);
    }
  }, [selected, watchlist.entries]);

  const handleAddTicker = useCallback(async (ticker: string) => {
    await watchlist.addTicker(ticker);
  }, [watchlist]);

  const handleRemoveTicker = useCallback(async (ticker: string) => {
    await watchlist.removeTicker(ticker);
    if (selected === ticker) setSelected(null);
  }, [watchlist, selected]);

  const handleAfterAIAction = useCallback(() => {
    void watchlist.refresh();
    void portfolio.refresh();
  }, [watchlist, portfolio]);

  const handleSelectTicker = useCallback((ticker: string) => {
    setSelected(ticker);
    setActiveTab("chart");
  }, []);

  return (
    <div className="flex h-[100dvh] flex-col bg-[#0d1117] text-[#e6edf3]">
      <Header
        totalValue={portfolio.portfolio?.total_value ?? null}
        cashBalance={portfolio.portfolio?.cash_balance ?? null}
        status={market.status}
        username={user.username}
        onLogout={onLogout}
      />

      {/* Desktop layout — unchanged */}
      <div className="hidden md:flex min-h-0 flex-1">
        <div className="w-96 min-w-[320px]">
          <WatchlistPanel
            entries={watchlist.entries}
            prices={market.prices}
            sparklines={market.sparklines}
            selected={selected}
            onSelect={setSelected}
            onAdd={handleAddTicker}
            onRemove={handleRemoveTicker}
          />
        </div>
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1">
            <MainChart ticker={selected} liveTick={selected ? market.prices[selected] : undefined} />
          </div>
          <div className="grid h-72 grid-cols-2 border-t border-[#30363d]">
            <PortfolioHeatmap positions={portfolio.portfolio?.positions ?? []} />
            <PnLChart history={portfolio.history} />
          </div>
          <div className="h-56">
            <PositionsTable positions={portfolio.portfolio?.positions ?? []} prices={market.prices} onSelect={setSelected} />
          </div>
          <TradeBar initialTicker={selected} onTrade={(req) => portfolio.executeTrade(req)} />
        </div>
        <ChatPanel open={chatOpen} onToggle={() => setChatOpen((o) => !o)} onActions={handleAfterAIAction} />
      </div>

      {/* Mobile layout — tab panels, kept mounted to preserve chart state */}
      <div className="flex min-h-0 flex-1 flex-col md:hidden">
        {/* Watchlist tab */}
        <div className={activeTab === "watchlist" ? "flex-1 overflow-hidden" : "hidden"}>
          <WatchlistPanel
            entries={watchlist.entries}
            prices={market.prices}
            sparklines={market.sparklines}
            selected={selected}
            onSelect={handleSelectTicker}
            onAdd={handleAddTicker}
            onRemove={handleRemoveTicker}
          />
        </div>

        {/* Chart tab */}
        <div className={activeTab === "chart" ? "flex flex-1 flex-col overflow-hidden" : "hidden"}>
          <div className="min-h-0 flex-1">
            <MainChart ticker={selected} liveTick={selected ? market.prices[selected] : undefined} />
          </div>
          <TradeBar initialTicker={selected} onTrade={(req) => portfolio.executeTrade(req)} />
        </div>

        {/* Portfolio tab */}
        <div className={activeTab === "portfolio" ? "flex flex-1 flex-col overflow-hidden" : "hidden"}>
          <div className="grid grid-cols-2 border-b border-[#30363d]" style={{ height: 192 }}>
            <PortfolioHeatmap positions={portfolio.portfolio?.positions ?? []} />
            <PnLChart history={portfolio.history} />
          </div>
          <div className="min-h-0 flex-1">
            <PositionsTable
              positions={portfolio.portfolio?.positions ?? []}
              prices={market.prices}
              onSelect={(ticker) => { setSelected(ticker); setActiveTab("chart"); }}
            />
          </div>
        </div>

        {/* Chat tab */}
        <div className={activeTab === "chat" ? "flex-1 overflow-hidden" : "hidden"}>
          <ChatPanel
            open={true}
            onToggle={() => setActiveTab("chart")}
            onActions={handleAfterAIAction}
          />
        </div>
      </div>

      {/* Mobile bottom tab bar */}
      <nav className="flex border-t border-[#30363d] bg-[#161b22] md:hidden" aria-label="Main navigation">
        {TABS.map(({ id, label, Icon }) => {
          const active = activeTab === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => setActiveTab(id)}
              className={`flex flex-1 flex-col items-center justify-center gap-1 py-2.5 transition-colors ${
                active ? "text-[#ecad0a]" : "text-[#8b949e] hover:text-[#e6edf3]"
              }`}
              aria-current={active ? "page" : undefined}
            >
              <Icon />
              <span className="text-[9px] uppercase tracking-widest">{label}</span>
            </button>
          );
        })}
      </nav>
    </div>
  );
}

export default function Page() {
  return (
    <AuthGate>
      {(user, onLogout) => <TradingApp user={user} onLogout={onLogout} />}
    </AuthGate>
  );
}
