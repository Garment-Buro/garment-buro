import type { CdekAction, CdekRequestBody } from './types.ts';

export const isCdekAction = (value: unknown): value is CdekAction => (
    value === 'calculate' || value === 'offices'
);

export const readCdekRequestBody = (value: unknown): CdekRequestBody => (
    value !== null && typeof value === 'object' && !Array.isArray(value)
        ? value as CdekRequestBody
        : {}
);

export const getCdekAction = (body: CdekRequestBody, queryAction: string | null) => (
    typeof body.action === 'string' && body.action ? body.action : queryAction
);

export const toCdekOfficeParams = (entries: Iterable<[string, unknown]>) => {
    const params = new URLSearchParams();

    for (const [key, value] of entries) {
        if (key !== 'action') params.set(key, String(value));
    }

    return params;
};
