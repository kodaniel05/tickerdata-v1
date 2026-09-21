"use client";

import { useEffect, useId, useRef, useState } from "react";
import { number, getMarket, sessionDate, type History, type Range } from "@/lib/market";

const ranges: Range[] = ["1m", "3m", "6m", "1y"];
const height = 190, left = 58, right = 18, top = 18, bottom = 35;

export default function PriceChart({ symbol }: { symbol: string }) {
  const [range, setRange] = useState<Range>("3m");
  const [history, setHistory] = useState<History | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [hover, setHover] = useState<number | null>(null);
  const gradient = useId();
  const container = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(960);
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(280, entry.contentRect.width)));
    if (container.current) observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    getMarket<History>(`/api/stocks/${encodeURIComponent(symbol)}/history/?range=${range}`, controller.signal)
      .then((data) => { if (!controller.signal.aborted) setHistory(data); })
      .catch((failure) => { if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "Market data is temporarily unavailable."); });
    return () => controller.abort();
  }, [symbol, range, attempt]);
  const data = history?.data ?? [];
  const prices = data.map((bar) => bar.close);
  const low = Math.min(...prices), high = Math.max(...prices);
  const padding = (high - low || high * 0.02 || 1) * 0.15;
  const min = low - padding, max = high + padding;
  const x = (index: number) => left + (data.length === 1 ? 0.5 : index / (data.length - 1)) * (width - left - right);
  const y = (price: number) => top + (max - price) / (max - min) * (height - top - bottom);
  const line = data.map((bar, index) => `${index ? "L" : "M"}${x(index)},${y(bar.close)}`).join(" ");
  const selected = hover == null ? null : data[hover];
  const ticks = [...new Set([0, Math.floor((data.length - 1) / 3), Math.floor(2 * (data.length - 1) / 3), data.length - 1])];

  return <section className="chart-section" aria-label="Closing price history">
    <div className="range-controls" aria-label="History range">
      {ranges.map((item) => <button key={item} aria-pressed={range === item} onClick={() => {
        if (range === item) return;
        setRange(item); setHistory(null); setError(""); setHover(null);
      }}>{item.toUpperCase()}</button>)}
    </div>
    <div ref={container} className="chart-area" aria-busy={!history && !error}>
      {error ? <div className="chart-message error-message" role="alert"><p>{error}</p><button onClick={() => { setError(""); setAttempt(attempt + 1); }}>Try again</button></div> : !history ? (
        <div className="chart-message" role="status">Loading price history…</div>
      ) : !data.length ? <div className="chart-message">No price history available.</div> : <>
        <svg className="price-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${symbol} closing prices, ${range}. Use arrow keys to explore.`}
          tabIndex={0} onBlur={() => setHover(null)} onMouseLeave={() => setHover(null)}
          onMouseMove={(event) => {
            const bounds = event.currentTarget.getBoundingClientRect();
            const position = ((event.clientX - bounds.left) / bounds.width * width - left) / (width - left - right);
            setHover(Math.max(0, Math.min(data.length - 1, Math.round(position * (data.length - 1)))));
          }} onKeyDown={(event) => {
            if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
              event.preventDefault();
              setHover((index) => Math.max(0, Math.min(data.length - 1, (index ?? 0) + (event.key === "ArrowRight" ? 1 : -1))));
            }
            if (event.key === "Escape") setHover(null);
          }}>
          <defs><linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1"><stop stopColor="#bdd8ff" stopOpacity=".55" /><stop offset="1" stopColor="#e8f2ff" stopOpacity=".12" /></linearGradient></defs>
          {[0, 1, 2, 3, 4].map((tick) => {
            const price = min + (max - min) * tick / 4;
            return <g key={tick}><line className="grid-line" x1={left} x2={width - right} y1={y(price)} y2={y(price)} /><text x={left - 12} y={y(price) + 4} textAnchor="end">{price.toLocaleString("en-US", { maximumFractionDigits: 2 })}</text></g>;
          })}
          <path d={`${line} L${x(data.length - 1)},${height - bottom} L${x(0)},${height - bottom} Z`} fill={`url(#${gradient})`} />
          <path d={line} fill="none" stroke="#075acb" strokeWidth="1.8" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
          {ticks.map((index) => <text key={index} x={x(index)} y={height - 9} textAnchor="middle">{sessionDate(data[index].date).replace(/, \d{4}$/, "")}</text>)}
          <circle cx={x(data.length - 1)} cy={y(data[data.length - 1].close)} r="3.5" fill="#075acb" />
          {selected && <><line x1={x(hover!)} x2={x(hover!)} y1={top} y2={height - bottom} stroke="#aec6e5" strokeDasharray="3 3" /><circle cx={x(hover!)} cy={y(selected.close)} r="4" fill="#075acb" /></>}
        </svg>
        {selected && <div className="chart-tooltip" role="status" style={{ left: `${Math.max(13, Math.min(87, x(hover!) / width * 100))}%` }}>
          <span>{sessionDate(selected.date)}</span><strong>Close {number(selected.close)}</strong>
        </div>}
      </>}
    </div>
  </section>;
}
