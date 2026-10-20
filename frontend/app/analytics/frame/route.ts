import { PUBLIC_ANALYTICS_FRAME_HTML } from '@/lib/analytics/frameDocument';

export function GET(request: Request) {
    const headers = {
        'Cache-Control': 'no-store',
        'Referrer-Policy': 'no-referrer',
        // Also enforced by the response: a future parent cannot relax the sandbox.
        'Content-Security-Policy': "sandbox allow-scripts; frame-ancestors 'self'",
        'X-Content-Type-Options': 'nosniff',
    };
    if (new URL(request.url).search) return new Response('Invalid request.', { status: 400, headers });
    return new Response(PUBLIC_ANALYTICS_FRAME_HTML, {
        headers: { ...headers, 'Content-Type': 'text/html; charset=utf-8' },
    });
}
