import { NextRequest, NextResponse } from 'next/server';

import {
    calculateCdekTariffs,
    CDEK_JSON_HEADERS,
    getCdekOffices,
    getCdekOfficesFromBody,
} from '@/lib/server/cdek/service';
import {
    getCdekAction,
    isCdekAction,
    readCdekRequestBody,
    toCdekOfficeParams,
} from '@/lib/server/cdek/utils';

const jsonError = (message: string, status: number) => NextResponse.json(
    { message },
    { status, headers: CDEK_JSON_HEADERS },
);

const serviceResponse = ({ data, status }: { data: unknown; status: number }) => NextResponse.json(
    data,
    { status, headers: CDEK_JSON_HEADERS },
);

const handleError = (error: unknown) => {
    console.error('[CDEK Service] Error:', error);
    return jsonError('Internal error', 500);
};

export async function GET(request: NextRequest) {
    const searchParams = new URL(request.url).searchParams;
    const action = searchParams.get('action');

    if (!action) return jsonError('Action is required', 400);
    if (action !== 'offices') return jsonError('Unknown action', 400);

    try {
        return serviceResponse(await getCdekOffices(toCdekOfficeParams(searchParams.entries())));
    } catch (error) {
        return handleError(error);
    }
}

export async function POST(request: NextRequest) {
    const body = readCdekRequestBody(await request.json().catch(() => ({})));
    const action = getCdekAction(body, new URL(request.url).searchParams.get('action'));

    if (!action) return jsonError('Action is required', 400);
    if (!isCdekAction(action)) return jsonError('Unknown action', 400);

    try {
        const result = action === 'calculate'
            ? await calculateCdekTariffs(body)
            : await getCdekOfficesFromBody(body);
        return serviceResponse(result);
    } catch (error) {
        return handleError(error);
    }
}
