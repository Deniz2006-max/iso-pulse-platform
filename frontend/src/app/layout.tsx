import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "İSO Pulse",
  description: "İnpulse & Outpulse platformu",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr">
      <body className="antialiased">{children}</body>
    </html>
  );
}
