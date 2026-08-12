import type { Metadata, Viewport } from "next";
import { Alumni_Sans_SC, IBM_Plex_Mono, Inter, Manrope, Questrial, Michroma } from "next/font/google";
import "./globals.css";
import "@aejkatappaja/phantom-ui/ssr.css";

const manrope = Manrope({
  variable: "--font-manrope",
  subsets: ["latin", "cyrillic"],
});

const questrial = Questrial({
  weight: "400",
  variable: "--font-questrial",
  subsets: ["latin"],
});

const michroma = Michroma({
  weight: "400",
  variable: "--font-michroma",
  subsets: ["latin"],
});

const inter = Inter({
  weight: ["400", "800"],
  style: ["normal", "italic"],
  variable: "--font-inter",
  subsets: ["latin", "cyrillic"],
});

const alumniSansSc = Alumni_Sans_SC({
  weight: "800",
  variable: "--font-alumni-sans-sc",
  subsets: ["latin", "cyrillic"],
  adjustFontFallback: false,
});

const ibmPlexMono = IBM_Plex_Mono({
  weight: "500",
  variable: "--font-ibm-plex-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    template: "Garment Buro | %s",
    default: "Garment Buro | Главная",
  },
  description: "Когда вещь почти подходит — можно её доработать.",
  manifest: "/manifest.webmanifest",
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
import { PhantomUiBootstrap } from "@/components/runtime/PhantomUiBootstrap";

export default function RootLayout({
  children,
  modal,
}: Readonly<{
  children: React.ReactNode;
  modal: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${manrope.variable} ${questrial.variable} ${michroma.variable} ${inter.variable} ${alumniSansSc.variable} ${ibmPlexMono.variable} font-manrope antialiased min-h-screen flex flex-col relative`}
      >
        <AppEnvironmentProvider>
          <AuthSessionBootstrap />
          <SplashBoundary>
            <Header />
            <main className="appPageShell flex-1">
              {children}
            </main>
            <Footer />

            {/* Global Modal / Banner overlays */}
            <CookieConsent />

            <PhantomUiBootstrap />
            <CartSyncBootstrap />

            {/* Popup modal slot (parallel routes) */}
            {modal}
          </SplashBoundary>
        </AppEnvironmentProvider>
      </body>
    </html>
  );
}
