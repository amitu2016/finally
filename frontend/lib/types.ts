export type ConnectionStatus = "connected" | "connecting" | "disconnected";

export interface PriceTick {
  ticker: string;
  price: number;
  prev_price: number;
  change_pct: number;
  timestamp: string;
  company_name: string;
}

export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  unrealized_pnl: number;
  pnl_pct: number;
}

export interface Portfolio {
  total_value: number;
  cash_balance: number;
  positions: Position[];
}

export interface PortfolioSnapshot {
  total_value: number;
  recorded_at: string;
}

export interface WatchlistEntry {
  ticker: string;
  price: number | null;
  prev_price: number | null;
  change_pct: number | null;
  company_name: string;
}

export interface TradeRequest {
  ticker: string;
  quantity: number;
  side: "buy" | "sell";
}

export interface TradeExecuted {
  ticker: string;
  side: "buy" | "sell";
  quantity: number;
  price?: number;
}

export interface WatchlistChange {
  ticker: string;
  action: "add" | "remove";
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  trades_executed?: TradeExecuted[];
  watchlist_changes?: WatchlistChange[];
  errors?: string[];
}
