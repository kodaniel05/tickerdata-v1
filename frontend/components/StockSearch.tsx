"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { Stock } from "@/lib/market";

export default function StockSearch({ compact = false, onSelect }: { compact?: boolean; onSelect: (stock: Stock) => void }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Stock[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [status, setStatus] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const listId = useId();

  useEffect(() => {
    if (!query.trim() || !open) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setStatus("Searching…");
      try {
        const response = await fetch(`/api/search/?q=${encodeURIComponent(query.trim())}`, { signal: controller.signal, cache: "no-store" });
        if (!response.ok) throw new Error("Search unavailable");
        const data: { results: Stock[] } = await response.json();
        if (controller.signal.aborted) return;
        setResults(data.results);
        setStatus(data.results.length ? "" : "No matches. Try another ticker or company.");
      } catch {
        if (!controller.signal.aborted) setStatus("Search is temporarily unavailable. Try again.");
      }
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [query, open]);

  function select(stock: Stock) {
    setOpen(false); setQuery(""); setResults([]); setStatus("");
    onSelect(stock);
  }

  return <div className={`stock-search ${compact ? "compact" : ""}`} onBlur={(event) => {
    if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
  }}>
    <div className="search-field">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></svg>
      <input ref={input} role="combobox" aria-label="Search ticker or company" aria-autocomplete="list"
        aria-expanded={open && !!query.trim()} aria-controls={listId}
        aria-activedescendant={open && results[active] ? `${listId}-${active}` : undefined}
        autoComplete="off" spellCheck={false} maxLength={80} value={query}
        placeholder={compact ? "Search another ticker or company…" : "Search ticker or company…"}
        onFocus={() => setOpen(true)}
        onChange={(event) => { setQuery(event.target.value); setResults([]); setActive(0); setStatus(""); setOpen(true); }}
        onKeyDown={(event) => {
          if (event.key === "Escape") { setOpen(false); return; }
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault(); setOpen(true);
            if (results.length) setActive((index) => (index + (event.key === "ArrowDown" ? 1 : -1) + results.length) % results.length);
          }
          if (event.key === "Enter" && open && results[active]) { event.preventDefault(); select(results[active]); }
        }} />
      {query && <button className="clear-search" aria-label="Clear search" onClick={() => {
        setQuery(""); setResults([]); setStatus(""); input.current?.focus();
      }}>×</button>}
    </div>
    {open && query.trim() && (results.length > 0 || status) && <div className="suggestions">
      <ul id={listId} role="listbox" aria-label="Stocks">
        {results.map((stock, index) => <li key={stock.symbol} id={`${listId}-${index}`} role="option"
          aria-selected={index === active} className={index === active ? "active" : ""}
          onMouseEnter={() => setActive(index)} onMouseDown={(event) => event.preventDefault()} onClick={() => select(stock)}>
          <strong>{stock.symbol}</strong><span>{stock.name}</span>
        </li>)}
      </ul>
      {status && <p className="search-status" role="status">{status}</p>}
    </div>}
  </div>;
}
