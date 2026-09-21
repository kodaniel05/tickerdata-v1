import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TickerData — Search a stock",
  description: "A quiet place to explore stock prices and statistics.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
