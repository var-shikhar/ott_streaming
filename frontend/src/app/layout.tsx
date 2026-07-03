import type { Metadata, Viewport } from "next";
import { Geist } from "next/font/google";
import "./globals.css";
import BottomNav from "@/components/BottomNav";
import PwaRegister from "@/components/PwaRegister";
import TopBar from "@/components/TopBar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Qisso — Reels, Series & Movies",
  description: "Every story, one scene at a time. Vertical micro-dramas and films — first episodes free.",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Qisso",
  },
  icons: {
    apple: "/icons/icon-180.png",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#09090b",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} antialiased`}>
      <body className="min-h-screen bg-black font-sans text-zinc-100">
        <PwaRegister />
        <div className="relative mx-auto flex min-h-dvh w-full max-w-md flex-col bg-zinc-950 sm:shadow-[0_0_40px_rgba(0,0,0,0.8)] sm:ring-1 sm:ring-zinc-800">
          <TopBar />
          <main className="flex-1 pb-20">{children}</main>
          <BottomNav />
        </div>
      </body>
    </html>
  );
}
