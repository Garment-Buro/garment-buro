export type CdekAction = 'calculate' | 'offices';

export type CdekRequestBody = Record<string, unknown> & {
    action?: unknown;
};

export type CdekServiceResponse = {
    data: unknown;
    status: number;
};
