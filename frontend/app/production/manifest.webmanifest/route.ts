import { NextResponse } from 'next/server';
export function GET() {
    return NextResponse.json(
        {
            id: '/production',
            name: 'Garment Buro — производство',
            short_name: 'GB Цех',
            start_url: '/production',
            scope: '/production',
            display: 'standalone',
            lang: 'ru',
            background_color: '#f2f0ef',
            theme_color: '#f2f0ef',
            icons: [
                {
                    src: '/pwa-icon-192.png',
                    sizes: '192x192',
                    type: 'image/png',
                    purpose: 'any',
                },
                {
                    src: '/pwa-icon-512.png',
                    sizes: '512x512',
                    type: 'image/png',
                    purpose: 'any',
                },
            ],
        },
        {
            headers: {
                'Content-Type': 'application/manifest+json',
                'Cache-Control': 'public, max-age=3600',
            },
        },
    );
}
