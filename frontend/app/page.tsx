import { LandingPage } from '@/components/shared/LandingPage';
import { CatalogPresentationOverlay } from '@/components/presentation/CatalogPresentationOverlay';
import { getCatalogData } from '@/lib/catalog/data';
import type { Metadata } from 'next';
import { Suspense } from 'react';

export const metadata: Metadata = {
  title: "Главная"
};

export default async function Home() {
  const { products, settings } = await getCatalogData();
  return (
    <>
      <LandingPage initialProducts={products} initialSettings={settings} />
      <Suspense fallback={null}>
        <CatalogPresentationOverlay />
      </Suspense>
    </>
  );
}
