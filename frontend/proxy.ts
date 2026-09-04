import type { NextRequest } from 'next/server';
import { NextResponse } from 'next/server';

/**
 * Set this to false to re-enable all frontend pages.
 */
const ADMIN_ONLY_MODE = false;

export function proxy(request: NextRequest) {
    const hostname = request.headers.get('host')?.split(':')[0].toLowerCase();
    const { pathname } = request.nextUrl;
    if (hostname === 'partner.garment-buro.ru') {
        if (pathname === '/' || (!pathname.startsWith('/partner') && !pathname.startsWith('/api'))) {
            const url = request.nextUrl.clone();
            url.pathname = '/partner';
            const response = NextResponse.rewrite(url);
            response.headers.set('X-Robots-Tag', 'noindex, nofollow');
            return response;
        }
        const response = NextResponse.next();
        response.headers.set('X-Robots-Tag', 'noindex, nofollow');
        return response;
    }

    if (!ADMIN_ONLY_MODE) {
        return NextResponse.next();
    }

    const isAllowed =
        pathname.startsWith('/admin') ||
        pathname.startsWith('/api') ||
        pathname.startsWith('/_next') ||
        pathname.startsWith('/uploads') ||
        pathname === '/favicon.ico' ||
        pathname.includes('.');

    if (isAllowed) {
        return NextResponse.next();
    }

    const url = request.nextUrl.clone();
    url.pathname = '/404';
    return NextResponse.rewrite(url);
}

export const config = {
    matcher: ['/((?!_next/static|_next/image|favicon.ico|uploads).*)'],
};
