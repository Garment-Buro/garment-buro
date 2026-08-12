const getServerApiBaseUrl = () => process.env.INTERNAL_API_URL || 'http://backend:8000';

const joinServerUrl = (path: string) => (
    `${getServerApiBaseUrl().replace(/\/$/, '')}/api/${path.replace(/^\//, '')}`
);

export const serverFetch = (path: string, init?: RequestInit) => (
    fetch(joinServerUrl(path), init)
);

export const serverRequest = async (path: string, init?: RequestInit) => {
    const response = await serverFetch(path, init);
    if (!response.ok) throw new Error(`Server API request failed with status ${response.status}`);
    return response;
};

export const serverRequestJson = async <Result>(
    path: string,
    init?: RequestInit,
): Promise<Result> => {
    const response = await serverRequest(path, init);
    return response.json() as Promise<Result>;
};
