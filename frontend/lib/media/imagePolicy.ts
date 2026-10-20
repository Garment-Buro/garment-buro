const PUBLIC_IMAGE_PREFIXES = ['/uploads/', '/mock/', '/nikitamoiseev/', '/production/', '/service-home/', '/_next/static/media/'];
const IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'webp', 'gif', 'avif', 'ico', 'svg'];

/** The optimizer creates a public cache, so API and signed URLs must never enter it. */
export const publicImageLocalPatterns = [
    ...IMAGE_EXTENSIONS.map(extension => ({ pathname: `/*.${extension}`, search: '' })),
    ...PUBLIC_IMAGE_PREFIXES.map(prefix => ({ pathname: `${prefix}**`, search: '' })),
];

export function canOptimizePublicImage(source: string): boolean {
    if (!source.startsWith('/') || source.startsWith('//') || source.includes('\\')) return false;
    try {
        const url = new URL(source, 'http://image.invalid');
        if (url.origin !== 'http://image.invalid' || url.search || url.hash) return false;
        const pathname = url.pathname;
        if (/%(?:2f|5c|25)/i.test(pathname)) return false;
        decodeURIComponent(pathname); // Reject malformed escapes before Next parses the source.
        return PUBLIC_IMAGE_PREFIXES.some(prefix => pathname.startsWith(prefix))
            || (!pathname.slice(1).includes('/') && IMAGE_EXTENSIONS.some(extension => pathname.endsWith(`.${extension}`)));
    } catch { return false; }
}
