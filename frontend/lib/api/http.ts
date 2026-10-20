import { readCheckoutPrices, type CheckoutItemPrice } from './checkoutPrices.ts';

export class ApiError extends Error {
    readonly status: number;
    readonly requestId: string | null;
    readonly code: string | null;
    readonly orderId: number | null;
    readonly retryAfter: number | null;
    readonly checkoutPrices: CheckoutItemPrice[] | null;

    constructor(
        message: string,
        status: number,
        requestId: string | null = null,
        metadata: { code?: string | null; orderId?: number | null; retryAfter?: number | null; checkoutPrices?: CheckoutItemPrice[] | null } = {},
    ) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.requestId = requestId;
        this.code = metadata.code ?? null;
        this.orderId = metadata.orderId ?? null;
        this.retryAfter = metadata.retryAfter ?? null;
        this.checkoutPrices = metadata.checkoutPrices ?? null;
    }
}

/**
 * Browser requests must stay on this application origin.
 *
 * Next.js rewrites `/api/*` to the private backend defined by
 * `INTERNAL_API_URL`. Keeping the browser base relative prevents deployment
 * configuration from exposing the backend or bypassing our application.
 */
export const getPublicApiBaseUrl = () => '/api';

/** Read only locally supplied raster bytes; never turn an arbitrary URL into an upload. */
export async function readLocalRasterImage(source: string, options: { origin: string; maxBytes: number; signal?: AbortSignal }): Promise<Blob> {
    options.signal?.throwIfAborted();
    const inline = /^data:image\/(?:png|jpeg|webp);base64,/i.test(source);
    const ownBlob = Boolean(options.origin) && source.startsWith(`blob:${options.origin}/`);
    if (!inline && !ownBlob) throw new Error('Изображение не связано с товаром или проектом. Загрузите свой файл заново.');
    if (inline && source.length > Math.ceil(options.maxBytes * 4 / 3) + 128) throw new Error('Изображение слишком большое.');
    const response = await fetch(source, { signal: options.signal });
    if (!response.ok) throw new Error('Не удалось прочитать изображение.');
    const blob = await response.blob();
    options.signal?.throwIfAborted();
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(blob.type) || !blob.size) throw new Error('Поддерживаются изображения PNG, JPEG и WebP.');
    if (blob.size > options.maxBytes) throw new Error('Изображение слишком большое.');
    return blob;
}

const joinUrl = (baseUrl: string, path: string) => (
    `${baseUrl.replace(/\/$/, '')}/${path.replace(/^\//, '')}`
);

const getError = async (response: Response) => {
    let code: string | null = null;
    let orderId: number | null = null;
    let checkoutPrices: CheckoutItemPrice[] | null = null;
    const getErrorMessage = async () => {
    try {
        const payload = await response.json() as { detail?: unknown; message?: unknown };
        if (payload.detail && typeof payload.detail === 'object' && !Array.isArray(payload.detail)) {
            const detail = payload.detail as Record<string, unknown>;
            checkoutPrices = readCheckoutPrices(detail, response.status);
            if (typeof detail.code === 'string' && /^[a-z_]{1,80}$/.test(detail.code)) code = detail.code;
            if (Number.isSafeInteger(detail.order_id) && (detail.order_id as number) > 0) orderId = detail.order_id as number;
        }
        if (typeof payload.detail === 'string' && payload.detail) return payload.detail;
        if (typeof payload.message === 'string' && payload.message) return payload.message;
        if (Array.isArray(payload.detail)) {
            const messages = payload.detail
                .map((item) => {
                    if (!item || typeof item !== 'object') return null;
                    const issue = item as { loc?: unknown; msg?: unknown };
                    if (typeof issue.msg !== 'string') return null;
                    const location = Array.isArray(issue.loc)
                        ? issue.loc.filter((part) => part !== 'body').join('.')
                        : '';
                    return location ? `${location}: ${issue.msg}` : issue.msg;
                })
                .filter((message): message is string => Boolean(message));
            if (messages.length) return messages.join('; ');
        }
        if (
            payload.detail &&
            typeof payload.detail === 'object' &&
            'message' in payload.detail &&
            typeof payload.detail.message === 'string'
        ) {
            return payload.detail.message;
        }
    } catch {
        // The status-based fallback below also covers non-JSON error responses.
    }

    return `API request failed with status ${response.status}`;
    };
    const message = await getErrorMessage();
    const retry = Number(response.headers.get('Retry-After'));
    return new ApiError(message, response.status, response.headers.get('X-Request-ID'), {
        code, orderId, checkoutPrices, retryAfter: Number.isFinite(retry) && retry > 0 && retry <= 3600 ? retry : null,
    });
};

export async function request(path: string, init?: RequestInit): Promise<Response> {
    const response = await fetch(joinUrl(getPublicApiBaseUrl(), path), {
        credentials: 'same-origin',
        ...init,
    });

    if (!response.ok) {
        throw await getError(response);
    }

    return response;
}

export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await request(path, init);
    return response.json() as Promise<T>;
}

export const PUBLIC_READ_TIMEOUT_MS = 10_000;

/** Side-effect-free reads, including private lists. No automatic retry. */
export async function requestReadJson<T>(path: string, init?: RequestInit): Promise<T> {
    const owner = init?.signal;
    owner?.throwIfAborted();
    const controller = new AbortController();
    const cancel = () => controller.abort(owner?.reason);
    owner?.addEventListener('abort', cancel, { once: true });
    const timer = setTimeout(() => controller.abort(
        new DOMException('Сервер не ответил вовремя. Попробуйте ещё раз.', 'TimeoutError'),
    ), PUBLIC_READ_TIMEOUT_MS);
    try {
        // Keep the deadline until the body (including an API error body) is read.
        const value = await requestJson<T>(path, { ...init, signal: controller.signal });
        controller.signal.throwIfAborted();
        return value;
    } catch (error) {
        // Error-body parsing can catch an abort; retain the actual timeout/cancel reason.
        controller.signal.throwIfAborted();
        throw error;
    } finally {
        clearTimeout(timer);
        owner?.removeEventListener('abort', cancel);
    }
}

/** Public reads retain the same deadline and cancellation protocol. */
export async function requestPublicJson<T>(path: string, init?: RequestInit): Promise<T> {
    return requestReadJson<T>(path, init);
}
