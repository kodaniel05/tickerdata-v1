"use client";

import { useEffect, useState } from "react";
import { number, getMarket, sessionDate, type Stock, type Summary } from "@/lib/market";
import PriceChart from "./PriceChart";
import MetricGrid from "./MetricGrid";

export default function StockOverview({ stock }: { stock: Stock }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    getMarket<Summary>(`/api/stocks/${encodeURIComponent(stock.symbol)}/`, controller.signal)
      .then((data) => { if (!controller.signal.aborted) setSummary(data); })
      .catch((failure) => { if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "Market data is temporarily unavailable."); });
    return () => controller.abort();
  }, [stock.symbol, attempt]);

  return <section aria-label={`${stock.symbol} analysis`}>
    <div className="overview-header">
    <header className="stock-heading">
      <h1>{stock.symbol}</h1>
      <p className="company-name">{stock.name}</p>
      <p className="session">{summary ? `Latest session · ${sessionDate(summary.as_of)}` : "Latest session"}</p>
    </header>
    {error ? <div className="error-message" role="alert"><p>{error}</p><button onClick={() => { setError(""); setAttempt(attempt + 1); }}>Try again</button></div> : <div className="price-row" aria-busy={!summary}>
      <div><span className="eyebrow">LATEST CLOSE</span><p className="stock-price">{number(summary?.price)}</p></div>
      <div className="opening-price"><span className="eyebrow">OPEN</span><p>{number(summary?.open)}</p></div>
      {!summary && <span className="loading-note" role="status">Loading market data…</span>}
    </div>}
    </div>
    <PriceChart symbol={stock.symbol} />
    <MetricGrid metrics={summary?.metrics} />
    <p className="currency-note">Price and traded value use the listing’s quote currency.</p>
  </section>;
}
