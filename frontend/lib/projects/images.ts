import type { ImageReference, ProjectImage } from './types.ts';
import { readLocalRasterImage } from '../api/http.ts';
import { isDesignImageUrl, readDesignImage } from '../api/designMedia.ts';

export const PROJECT_IMAGE_MAX_BYTES = 8 * 1024 * 1024;

export function createProjectImageResolver(options: {
    origin: string;
    references: Map<string, ImageReference>;
    upload: (image: Blob, signal?: AbortSignal) => Promise<Pick<ProjectImage, 'id'>>;
}) {
    return async (source: string, signal?: AbortSignal): Promise<ImageReference> => {
        signal?.throwIfAborted();
        const known = options.references.get(source);
        if (known) return { ...known };
        const blob = isDesignImageUrl(source) ? await readDesignImage(source, signal)
            : await readLocalRasterImage(source, { origin: options.origin, maxBytes: PROJECT_IMAGE_MAX_BYTES, signal });
        const media = await options.upload(blob, signal);
        signal?.throwIfAborted();
        const reference = { mediaId: media.id };
        options.references.set(source, reference);
        return { ...reference };
    };
}
