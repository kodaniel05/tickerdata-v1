export type Stock = { symbol: string; name: string };
export type Range = "1m" | "3m" | "6m" | "1y";
export type Summary = {
  symbol: string; as_of: string; price: number | null; open: number | null;
  metrics: Record<string, number | null>;
};
export type Bar = { date: string; open: number; high: number; low: number; close: number; volume: number };
export type History = { symbol: string; range: Range; as_of: string; data: Bar[] };

export async function getMarket<T>(path: string, signal: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { signal, cache: "no-store" });
  } catch {
    throw new Error("Market data is temporarily unavailable. Please try again.");
  }
  if (!response.ok) {
    const messages: Record<number, string> = {
      400: "That doesn’t look like a valid ticker.",
      404: "No market data was available for this stock.",
    };
    throw new Error(messages[response.status] ?? "Market data is temporarily unavailable. Please try again.");
  }
  return response.json();
}

export function number(value: number | null | undefined, suffix = "", signed = false) {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${signed && value > 0 ? "+" : ""}${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}${suffix}`;
}

export function sessionDate(value: string) {
  // Preserve the API's session date instead of shifting it into local time.
  return new Date(`${value.slice(0, 10)}T12:00:00Z`).toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric", timeZone: "UTC",
  });
}
