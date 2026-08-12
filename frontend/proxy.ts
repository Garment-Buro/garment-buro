import type { NextRequest } from 'next/server';
import { NextResponse } from 'next/server';

/**
 * Set this to false to re-enable all frontend pages.
 */
const ADMIN_ONLY_MODE = false;

export function proxy(request: NextRequest) {
    if (!ADMIN_ONLY_MODE) {
        return NextResponse.next();
    }

    const { pathname } = request.nextUrl;
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
