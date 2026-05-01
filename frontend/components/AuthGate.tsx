"use client";

import { useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { clearAuth, getUser, isAuthenticated, saveAuth, type AuthUser } from "@/lib/auth";

interface AuthGateProps {
  children: (user: AuthUser, onLogout: () => void) => ReactNode;
}

export function AuthGate({ children }: AuthGateProps) {
  const [authed, setAuthed] = useState(() => isAuthenticated());
  const [user, setUser] = useState<AuthUser | null>(() => getUser());

  if (authed && user) {
    return <>{children(user, () => { clearAuth(); setAuthed(false); setUser(null); })}</>;
  }

  return (
    <AuthScreen
      onSuccess={(token, u) => {
        saveAuth(token, u);
        setUser(u);
        setAuthed(true);
      }}
    />
  );
}

function AuthScreen({ onSuccess }: { onSuccess: (token: string, user: AuthUser) => void }) {
  const [tab, setTab] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = tab === "login"
        ? await api.login(username, password)
        : await api.register(username, password);
      onSuccess(res.token, { user_id: res.user_id, username: res.username });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-screen w-screen items-center justify-center bg-[#0d1117]">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="mb-8 text-center">
          <span className="text-2xl font-bold tracking-tight text-[#ecad0a]">FinAlly</span>
          <p className="mt-1 text-xs text-[#8b949e] uppercase tracking-widest">AI Trading Workstation</p>
        </div>

        {/* Card */}
        <div className="rounded-lg border border-[#30363d] bg-[#161b22] p-8">
          {/* Tabs */}
          <div className="mb-6 flex rounded-md border border-[#30363d] p-0.5">
            {(["login", "register"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => { setTab(t); setError(null); }}
                className={`flex-1 rounded py-1.5 text-xs font-semibold uppercase tracking-wider transition-colors ${
                  tab === t
                    ? "bg-[#209dd7] text-white"
                    : "text-[#8b949e] hover:text-[#e6edf3]"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-[#8b949e] uppercase tracking-wider">
                Username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. trader123"
                required
                autoFocus
                className="w-full rounded border border-[#30363d] bg-[#0d1117] px-3 py-2 text-sm text-[#e6edf3] placeholder-[#484f58] outline-none focus:border-[#209dd7] focus:ring-1 focus:ring-[#209dd7]"
              />
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-medium text-[#8b949e] uppercase tracking-wider">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={tab === "register" ? "Min. 6 characters" : ""}
                required
                className="w-full rounded border border-[#30363d] bg-[#0d1117] px-3 py-2 text-sm text-[#e6edf3] placeholder-[#484f58] outline-none focus:border-[#209dd7] focus:ring-1 focus:ring-[#209dd7]"
              />
            </div>

            {error && (
              <p className="rounded border border-[#ef4444]/30 bg-[#ef4444]/10 px-3 py-2 text-xs text-[#ef4444]">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded bg-[#753991] py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#8f46b0] disabled:opacity-50"
            >
              {loading ? "Please wait…" : tab === "login" ? "Sign In" : "Create Account"}
            </button>
          </form>

          {tab === "register" && (
            <p className="mt-4 text-center text-xs text-[#8b949e]">
              You'll start with{" "}
              <span className="text-[#ecad0a] font-semibold">₹1,00,000</span> in virtual cash
              and the default watchlist.
            </p>
          )}
        </div>

        <p className="mt-4 text-center text-xs text-[#484f58]">
          Simulated trading only — no real money involved.
        </p>
      </div>
    </div>
  );
}
