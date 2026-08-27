import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { ClientOnly } from "@/components/ClientOnly";

export const metadata: Metadata = {
  title: "LineTwin.ai — Simulation-only Digital Twin",
  description:
    "A local, simulation-only digital twin that infers station health and bottlenecks across a 40-station automotive assembly line — including where sensors are missing or dark.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <Providers>
          <ClientOnly>{children}</ClientOnly>
        </Providers>
      </body>
    </html>
  );
}
