"use client";

import { useCallback, useEffect, useState } from "react";
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

function TradingApp({ user, onLogout }: { user: AuthUser; onLogout: () => void }) {
  const market = useMarketData();
  const portfolio = usePortfolio();
  const watchlist = useWatchlist();
  const [selected, setSelected] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(true);

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

  return (
    <div className="flex h-screen flex-col bg-[#0d1117] text-[#e6edf3]">
      <Header
        totalValue={portfolio.portfolio?.total_value ?? null}
        cashBalance={portfolio.portfolio?.cash_balance ?? null}
        status={market.status}
        username={user.username}
        onLogout={onLogout}
      />
      <div className="flex min-h-0 flex-1">
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
