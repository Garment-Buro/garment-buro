import type { Metadata } from 'next';

import { PlatformEntry } from '@/components/platform/PlatformEntry';

export const metadata: Metadata = {
  title: 'Совместные коллекции',
  description: 'Платформа GARMENT BURO для совместных коллекций, кастомизации, производства и доставки.',
};

export default function Home() {
  return <PlatformEntry />;
}
