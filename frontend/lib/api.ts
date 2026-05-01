import type {
  Portfolio,
  PortfolioSnapshot,
  TradeRequest,
  WatchlistEntry,
  WatchlistChange,
  TradeExecuted,
} from "@/lib/types";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("finally_token");
}

function authHeaders(): HeadersInit {
  const token = getToken();
  return token
    ? { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }
    : { "Content-Type": "application/json" };
}

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(path, {
    headers: authHeaders(),
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      // ignore parse errors
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

interface AuthResponse {
  token: string;
  user_id: string;
  username: string;
}

interface ChatApiResponse {
  message: string;
  trades_executed: TradeExecuted[];
  watchlist_changes_applied: WatchlistChange[];
  errors: string[];
}

export interface ChatResponse {
  message: string;
  trades_executed: TradeExecuted[];
  watchlist_changes: WatchlistChange[];
  errors: string[];
}

export const api = {
  login(username: string, password: string): Promise<AuthResponse> {
    return request<AuthResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
  },

  register(username: string, password: string): Promise<AuthResponse> {
    return request<AuthResponse>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
  },

  guestLogin(): Promise<AuthResponse> {
    return request<AuthResponse>("/api/auth/guest", { method: "POST" });
  },

  getPortfolio(): Promise<Portfolio> {
    return request<Portfolio>("/api/portfolio");
  },

  getPortfolioHistory(): Promise<PortfolioSnapshot[]> {
    return request<PortfolioSnapshot[]>("/api/portfolio/history");
  },

  trade(req: TradeRequest): Promise<Portfolio> {
    return request<Portfolio>("/api/portfolio/trade", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  getWatchlist(): Promise<WatchlistEntry[]> {
    return request<WatchlistEntry[]>("/api/watchlist");
  },

  addWatchlist(ticker: string): Promise<WatchlistEntry[]> {
    return request<WatchlistEntry[]>("/api/watchlist", {
      method: "POST",
      body: JSON.stringify({ ticker }),
    });
  },

  removeWatchlist(ticker: string): Promise<WatchlistEntry[]> {
    return request<WatchlistEntry[]>(`/api/watchlist/${encodeURIComponent(ticker)}`, {
      method: "DELETE",
    });
  },

  async chat(message: string): Promise<ChatResponse> {
    const res = await request<ChatApiResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message }),
    });
    return {
      message: res.message,
      trades_executed: res.trades_executed,
      watchlist_changes: res.watchlist_changes_applied,
      errors: res.errors,
    };
  },
};
