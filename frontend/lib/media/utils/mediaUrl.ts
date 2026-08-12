export const normalizeMediaUrl = (raw?: string | null) => {
    if (!raw) return '';
    const url = raw.trim();
    if (!url) return '';

    if (
        url.startsWith('http://')
        || url.startsWith('https://')
        || url.startsWith('//')
        || url.startsWith('data:')
        || url.startsWith('blob:')
    ) {
        return url;
    }

    return url.startsWith('/') ? url : `/${url}`;
};

export const parseMediaCsv = (raw?: string | null) => raw
    ? raw.split(',').map(normalizeMediaUrl).filter(Boolean)
    : [];

export const isVideoUrl = (url: string) => /\.(mp4|webm|ogg|mov|m4v)(\?.*)?$/i.test(url);
