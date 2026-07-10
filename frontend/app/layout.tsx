import type { Metadata } from "next";

import { defaultDensity } from "@/design-system/tokens";

import "./globals.css";

export const metadata: Metadata = {
  title: "Provision",
  description: "Expert-reviewed, quantified regulatory-exposure memos for deal teams.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-GB" data-density={defaultDensity}>
      <body>{children}</body>
    </html>
  );
}
