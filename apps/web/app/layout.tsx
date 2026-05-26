import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import Providers from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgentLens — Premium AI Agent Observability",
  description: "Complete real-time visibility into autonomous AI agent execution",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ClerkProvider>
      <html lang="en" className="dark" suppressHydrationWarning>
        <body className="min-h-screen bg-slate-950 text-slate-50 antialiased selection:bg-indigo-500/30" suppressHydrationWarning>
          <Providers>{children}</Providers>
        </body>
      </html>
    </ClerkProvider>
  );
}
