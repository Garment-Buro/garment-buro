import { bearerHeaders } from './headers.ts';
import { request, requestJson } from './http.ts';

export const DESIGN_IMAGE_MAX_BYTES = 8 * 1024 * 1024;
export const isDesignImageUrl = (value: string) => /^\/api\/design-media\/[A-Za-z0-9_-]{43}\/content$/.test(value);
export type DesignImage = { url: string; content_type: string; size_bytes: number; expires_at: string };
export type ImportedDesignImage = DesignImage & { media_id: number };

function readImage(value: unknown): DesignImage {
    const image = value as DesignImage | null;
    if (!image || typeof image.url !== 'string' || !isDesignImageUrl(image.url)
        || !['image/png', 'image/jpeg', 'image/webp'].includes(image.content_type)
        || !Number.isSafeInteger(image.size_bytes) || image.size_bytes < 1 || image.size_bytes > DESIGN_IMAGE_MAX_BYTES
        || typeof image.expires_at !== 'string' || !Number.isFinite(Date.parse(image.expires_at))) {
        throw new Error('Сервер не подтвердил сохранение изображения. Попробуйте ещё раз.');
    }
    return { url: image.url, content_type: image.content_type, size_bytes: image.size_bytes, expires_at: image.expires_at };
}

export async function uploadDesignImage(image: Blob, signal?: AbortSignal): Promise<DesignImage> {
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(image.type)
        || !image.size || image.size > DESIGN_IMAGE_MAX_BYTES) throw new RangeError('Выберите JPEG, PNG или WebP размером до 8 МБ.');
    return readImage(await requestJson<unknown>('/design-media', {
        method: 'POST', headers: { 'Content-Type': image.type }, body: image, cache: 'no-store', signal,
    }));
}

export async function importDesignImages(mediaIds: number[], token: string, signal?: AbortSignal): Promise<ImportedDesignImage[]> {
    const ids = [...new Set(mediaIds)];
    if (!ids.length || ids.length > 102 || ids.some(id => !Number.isInteger(id) || id < 1 || id > 2_147_483_647)) {
        throw new RangeError('Неверные изображения проекта. Откройте проект заново.');
    }
    const value = await requestJson<{ items?: unknown }>('/design-media/import', {
        method: 'POST', headers: { ...bearerHeaders(token), 'Content-Type': 'application/json' },
        body: JSON.stringify({ media_ids: ids }), cache: 'no-store', signal,
    });
    if (!Array.isArray(value?.items) || value.items.length !== ids.length) throw new Error('Сервер не подтвердил все изображения проекта.');
    const seen = new Set<number>();
    return value.items.map(value => {
        const id = (value as ImportedDesignImage | null)?.media_id;
        if (typeof id !== 'number' || !ids.includes(id) || seen.has(id)) throw new Error('Сервер не подтвердил все изображения проекта.');
        seen.add(id);
        return { ...readImage(value), media_id: id };
    });
}

/** Copy a cart image into an owned project through the existing private upload. */
export async function readDesignImage(url: string, signal?: AbortSignal): Promise<Blob> {
    if (!isDesignImageUrl(url)) throw new Error('Неверная ссылка изображения дизайна.');
    const response = await request(url.slice('/api'.length), { cache: 'no-store', referrerPolicy: 'no-referrer', signal });
    const type = response.headers.get('Content-Type')?.split(';')[0] || '';
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(type) || !response.body) throw new Error('Не удалось прочитать изображение дизайна.');
    const reader = response.body.getReader(), chunks: Uint8Array<ArrayBuffer>[] = [];
    let size = 0;
    try {
        while (true) {
            signal?.throwIfAborted();
            const { done, value } = await reader.read();
            if (done) break;
            size += value.byteLength;
            if (size > DESIGN_IMAGE_MAX_BYTES) throw new Error('Изображение слишком большое.');
            chunks.push(value);
        }
        signal?.throwIfAborted();
        if (!size) throw new Error('Изображение пустое.');
        return new Blob(chunks, { type });
    } finally {
        await reader.cancel().catch(() => {});
        reader.releaseLock();
    }
}
