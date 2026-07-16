import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "SPY/QQQ Paper-Trading Bot",
  description: "Live dashboard for the SPY/QQQ Claude-gated RSI(2) swing bot",
};

const NAV_LINKS = [
  { href: "/", label: "Overview" },
  { href: "/signals", label: "Signals" },
  { href: "/posture", label: "Posture" },
  { href: "/trades", label: "Trades" },
  { href: "/strategy", label: "Strategy" },
];

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-page text-ink-primary">
        <header className="border-b border-border bg-surface">
          <div className="mx-auto max-w-5xl px-6 py-4 flex items-center justify-between flex-wrap gap-3">
            <Link href="/" className="font-semibold tracking-tight">
              SPY/QQQ Bot
            </Link>
            <nav className="flex gap-1 text-sm">
              {NAV_LINKS.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="px-3 py-1.5 rounded-md text-ink-secondary hover:text-ink-primary hover:bg-page transition-colors"
                >
                  {link.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <main className="flex-1 mx-auto w-full max-w-5xl px-6 py-8">{children}</main>
        <footer className="border-t border-border bg-surface">
          <div className="mx-auto max-w-5xl px-6 py-4 text-xs text-ink-muted">
            Paper trading only -- no real capital at risk. Not investment advice.
          </div>
        </footer>
      </body>
    </html>
  );
}
