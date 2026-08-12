export const bearerHeaders = (token?: string): Record<string, string> => (
    token ? { Authorization: `Bearer ${token}` } : {}
);
