import { Suspense } from "react";
import type { Metadata, Viewport } from "next";
import { Alumni_Sans_SC, IBM_Plex_Mono, Inter, Manrope, Questrial, Michroma } from "next/font/google";
import "./globals.css";

const manrope = Manrope({
  variable: "--font-manrope",
  subsets: ["latin", "cyrillic", "latin-ext"],
  // Include the currency glyphs used by catalog prices in the critical font.
  // Other families remain available through their variables and load on use.
  preload: true,
});

const questrial = Questrial({
  preload: false,
  weight: "400",
  variable: "--font-questrial",
  subsets: ["latin"],
});

const michroma = Michroma({
  preload: false,
  weight: "400",
  variable: "--font-michroma",
  subsets: ["latin"],
});

const inter = Inter({
  preload: false,
  weight: ["400", "800"],
  style: ["normal", "italic"],
  variable: "--font-inter",
  subsets: ["latin", "cyrillic"],
});

const alumniSansSc = Alumni_Sans_SC({
  preload: false,
  weight: "800",
  variable: "--font-alumni-sans-sc",
  subsets: ["latin", "cyrillic"],
  adjustFontFallback: false,
});

const ibmPlexMono = IBM_Plex_Mono({
  preload: false,
  weight: "500",
  variable: "--font-ibm-plex-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "https://garment-buro.ru"),
  title: {
    template: "Garment Buro | %s",
    default: "Garment Buro | Главная",
  },
  description: "Совместные коллекции, конструктор одежды, производство и доставка GARMENT BURO.",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    title: "Garment Buro",
  },
  icons: {
    icon: "/favicon.ico",
    apple: "/apple-touch-icon.png",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  colorScheme: "light",
  themeColor: "#F2F2F2",
};

import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { AppEnvironmentProvider } from "@/providers/AppEnvironmentProvider";
import { AuthSessionBootstrap } from "@/providers/AuthSessionBootstrap";
import { SplashBoundary } from "@/providers/SplashBoundary";
import { CookieConsent } from "@/components/shared/CookieConsent";

import { CartSyncBootstrap } from "@/components/cart/CartSyncBootstrap";
import { PwaRegistration } from "@/components/pwa/PwaRegistration";
import { YandexMetrika } from "@/components/analytics/YandexMetrika";

export default function RootLayout({
  children,
  modal,
}: Readonly<{
  children: React.ReactNode;
  modal: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body
        className={`${manrope.variable} ${questrial.variable} ${michroma.variable} ${inter.variable} ${alumniSansSc.variable} ${ibmPlexMono.variable} font-manrope antialiased min-h-screen flex flex-col relative`}
      >
        <AppEnvironmentProvider>
          <Suspense fallback={null}>
            <YandexMetrika />
          </Suspense>
          <AuthSessionBootstrap />
          <PwaRegistration />
          <SplashBoundary>
            <Header />
            <main className="appPageShell flex-1">
              {children}
            </main>
            <Footer />

            {/* Global Modal / Banner overlays */}
            <CookieConsent />

            <CartSyncBootstrap />

            {/* Popup modal slot (parallel routes) */}
            {modal}
          </SplashBoundary>
        </AppEnvironmentProvider>
      </body>
    </html>
  );
}
