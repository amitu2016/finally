"use client";

import { useState } from "react";

interface Props {
  onAdd: (ticker: string) => Promise<void>;
}

export function AddTickerForm({ onAdd }: Props) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await onAdd(value);
      setValue("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="flex gap-2 border-t border-[#30363d] p-2">
      <input
        value={value}
        onChange={(e) => setValue(e.target.value.toUpperCase())}
        placeholder="Add ticker (e.g. WIPRO)"
        className="flex-1 rounded border border-[#30363d] bg-[#0d1117] px-2 py-1 font-mono text-xs text-[#e6edf3] outline-none focus:border-[#209dd7]"
      />
      <button
        type="submit"
        disabled={busy || !value.trim()}
        className="rounded bg-[#209dd7] px-3 py-1 text-xs font-semibold text-[#0d1117] disabled:opacity-40"
      >
        Add
      </button>
      {error && (
        <span className="text-[10px] text-[#ef4444]" role="alert">
          {error}
        </span>
      )}
    </form>
  );
}
