import { NextResponse } from 'next/server';

const manifest = {
    id: '/partner',
    name: 'Garment Buro — партнёры',
    short_name: 'GB Партнёры',
    description: 'Кабинет партнёра Garment Buro.',
    start_url: '/partner',
    scope: '/partner',
    display: 'standalone',
    orientation: 'portrait-primary',
    lang: 'ru',
    background_color: '#E7EEF1',
    theme_color: '#E7EEF1',
    icons: [
        {
            src: '/pwa-icon-192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any',
        },
        {
            src: '/pwa-icon-192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'maskable',
        },
        {
            src: '/pwa-icon-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any',
        },
        {
            src: '/pwa-icon-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
        },
    ],
};

export function GET() {
    return NextResponse.json(manifest, {
        headers: {
            'Cache-Control': 'public, max-age=3600',
            'Content-Type': 'application/manifest+json',
        },
    });
}
