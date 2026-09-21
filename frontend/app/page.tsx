"use client";

import { useState } from "react";
import StockSearch from "@/components/StockSearch";
import StockOverview from "@/components/StockOverview";
import type { Stock } from "@/lib/market";

export default function Home() {
  const [stock, setStock] = useState<Stock | null>(null);
  return (
    <main className={stock ? "page analysis" : "page intro"}>
      {stock ? <>
        <StockSearch compact onSelect={setStock} />
        <StockOverview key={stock.symbol} stock={stock} />
      </> : <>
        <div className="intro-content">
          <h1>Search a stock</h1>
          <p>Look up a company by ticker or name.</p>
          <StockSearch onSelect={setStock} />
        </div>
        <svg className="intro-waves" viewBox="0 0 1440 400" preserveAspectRatio="none" aria-hidden="true">
          <path d="M0 280 Q270 50 570 240 T1100 170 T1440 90 V400 H0Z" fill="#edf4fb" />
          <path d="M0 350 Q270 170 570 310 T1100 250 T1440 160 V400 H0Z" fill="#f7faff" />
          <path d="M0 310 Q270 80 570 270 T1100 200 T1440 120" fill="none" stroke="#dfeefa" />
        </svg>
      </>}
    </main>
  );
}
