import type { Metadata } from 'next';

import { ServerPlatformEntry } from '@/components/platform/ServerPlatformEntry';

export const metadata: Metadata = {
  title: 'Главная',
  description: 'Платформа GARMENT BURO для совместных коллекций, кастомизации, производства и доставки.',
  appleWebApp: {
    capable: true,
    title: 'Garment Buro',
    statusBarStyle: 'black-translucent',
  },
};

export default function Home() {
  return <ServerPlatformEntry />;
}
