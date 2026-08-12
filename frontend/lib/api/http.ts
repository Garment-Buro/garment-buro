export class ApiError extends Error {
    readonly status: number;

    constructor(
        message: string,
        status: number,
    ) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
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

const joinUrl = (baseUrl: string, path: string) => (
    `${baseUrl.replace(/\/$/, '')}/${path.replace(/^\//, '')}`
);

const getErrorMessage = async (response: Response) => {
    try {
        const payload = await response.json() as { detail?: unknown; message?: unknown };
        if (typeof payload.detail === 'string' && payload.detail) return payload.detail;
        if (typeof payload.message === 'string' && payload.message) return payload.message;
    } catch {
        // The status-based fallback below also covers non-JSON error responses.
    }

    return `API request failed with status ${response.status}`;
};

export async function request(path: string, init?: RequestInit): Promise<Response> {
    const response = await fetch(joinUrl(getPublicApiBaseUrl(), path), {
        credentials: 'same-origin',
        ...init,
    });

    if (!response.ok) {
        throw new ApiError(
            await getErrorMessage(response),
            response.status,
        );
    }

    return response;
}

export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await request(path, init);
    return response.json() as Promise<T>;
}

export async function requestOptionalJson<T>(
    path: string,
    init?: RequestInit,
): Promise<T | null> {
    const response = await fetch(joinUrl(getPublicApiBaseUrl(), path), {
        credentials: 'same-origin',
        ...init,
    });
    if (!response.ok) return null;
    return response.json() as Promise<T>;
}
