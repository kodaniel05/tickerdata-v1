import { number } from "@/lib/market";

const metrics = [
  ["sma_20", "SMA 20", "Simple average · 20 sessions"],
  ["ema_20", "EMA 20", "Exponential average · 20 sessions"],
  ["rsi_14", "RSI 14", "Momentum · 14 sessions"],
  ["return_30d", "30D RETURN", "Cumulative change · 30 sessions"],
  ["volatility_20d", "DAILY VOLATILITY", "Daily return variability · 20 sessions"],
  ["adr_20d", "ADR 20", "Average high / low range · 20 sessions"],
  ["average_return_30d", "AVG DAILY RETURN", "Arithmetic mean · 30 sessions"],
  ["average_dollar_volume_20d", "AVG DOLLAR VOLUME", "Close × volume · 20-session average"],
];

export default function MetricGrid({ metrics: values }: { metrics?: Record<string, number | null> }) {
  return <section className="statistics" aria-label="Key statistics">
    <h2 className="eyebrow">KEY STATISTICS</h2>
    <dl className="metric-grid">
      {metrics.map(([key, label, context]) => {
        const value = values?.[key];
        const available = value != null && Number.isFinite(value);
        const directional = key === "return_30d" || key === "average_return_30d";
        const percent = directional || key === "volatility_20d" || key === "adr_20d";
        let formatted = number(value, percent ? "%" : "", directional);
        if (key === "average_dollar_volume_20d" && available) {
          // Backend dollar volume is already in millions, not raw dollars.
          formatted = `${(value >= 1000 ? value / 1000 : value).toLocaleString("en-US", { maximumFractionDigits: 1, minimumFractionDigits: 1 })}${value >= 1000 ? "B" : "M"}`;
        }
        return <div className="metric" key={key}>
          <dt>{label}</dt>
          <dd className={directional && available && value !== 0 ? (value > 0 ? "positive" : "negative") : ""}>{formatted}</dd>
          {key !== "rsi_14" && <dd className="metric-context">{context}</dd>}
          {key === "rsi_14" && available && <div className="rsi" aria-label={`RSI ${number(value)}, reference levels 30 and 70`}>
            <div className="rsi-track"><span style={{ left: `${Math.max(0, Math.min(100, value))}%` }} /></div>
            <div className="rsi-labels"><span>30</span><span>50</span><span>70</span></div>
          </div>}
        </div>;
      })}
    </dl>
  </section>;
}
