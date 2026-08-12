import { normalizeMediaUrl } from '@/lib/media/utils/mediaUrl';
import { assertSupportedMediaFile } from '@/lib/media/utils/upload';

import { requestJson } from './http';
import { bearerHeaders } from './headers';

type UploadResponse = {
    url: string;
};

export const uploadMediaFile = async (file: File, token?: string) => {
    assertSupportedMediaFile(file);
    const body = new FormData();
    body.append('file', file);

    const uploaded = await requestJson<UploadResponse>('/upload', {
        method: 'POST',
        headers: bearerHeaders(token),
        body,
    });

    return normalizeMediaUrl(uploaded.url);
};
