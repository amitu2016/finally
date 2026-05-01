"use client";

import { useEffect, useRef, useState } from "react";
import { formatINR } from "@/lib/format";

interface Props {
  price: number | null | undefined;
}

export function PriceCell({ price }: Props) {
  const [flash, setFlash] = useState<"" | "flash-up" | "flash-down">("");
  const previous = useRef<number | null | undefined>(price);

  useEffect(() => {
    const prev = previous.current;
    if (price !== null && price !== undefined && prev !== null && prev !== undefined) {
      if (price > prev) setFlash("flash-up");
      else if (price < prev) setFlash("flash-down");
    }
    previous.current = price;
  }, [price]);

  useEffect(() => {
    if (!flash) return;
    const t = setTimeout(() => setFlash(""), 500);
    return () => clearTimeout(t);
  }, [flash]);

  return (
    <span className={`inline-block rounded px-1.5 py-0.5 font-mono ${flash}`}>
      {formatINR(price ?? null)}
    </span>
  );
}
