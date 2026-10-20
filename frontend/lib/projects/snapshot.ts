import type { ConstructorDraftState } from '../constructor/types.ts';
import type { ImageReference, ProjectSnapshot } from './types.ts';

type ImageResolver = (source: string, signal?: AbortSignal) => Promise<ImageReference>;

export async function serializeProjectSnapshot(
    draft: ConstructorDraftState,
    resolve: ImageResolver,
    signal?: AbortSignal,
): Promise<ProjectSnapshot> {
    signal?.throwIfAborted();
    const copy = structuredClone(draft);
    const { customization } = copy;
    // Project documents already store this mapping at the root. Cart/order
    // customizations carry it themselves; do not duplicate it in project JSON.
    delete customization.geometry;
    const sources = [
        customization.modelImages.front,
        customization.modelImages.back,
        ...customization.decorations.map((item) => item.image),
    ];
    const references = new Map<string, ImageReference>();
    for (const source of new Set(sources)) {
        signal?.throwIfAborted();
        const reference = await resolve(source, signal);
        signal?.throwIfAborted();
        if (
            !Number.isInteger(reference.mediaId) ||
            reference.mediaId <= 0 ||
            reference.mediaId > 2_147_483_647
        ) {
            throw new RangeError('A persisted image ID is required');
        }
        references.set(source, { mediaId: reference.mediaId });
    }
    const image = (source: string) => {
        const reference = references.get(source);
        if (!reference) throw new Error('Project image was not resolved');
        return reference;
    };
    return {
        ...copy,
        schemaVersion: 1,
        customization: {
            ...customization,
            modelImages: {
                front: image(customization.modelImages.front),
                back: image(customization.modelImages.back),
            },
            decorations: customization.decorations.map((item) => ({
                ...item,
                image: image(item.image),
            })),
        },
    };
}

export function restoreProjectSnapshot(
    snapshot: ProjectSnapshot,
    images: ReadonlyArray<{ id: number; url: string }>,
): ConstructorDraftState {
    if (snapshot.schemaVersion !== 1) throw new Error('Unsupported project document version');
    const urls = new Map<number, string>();
    for (const image of images) {
        if (!image.url || (urls.has(image.id) && urls.get(image.id) !== image.url)) {
            throw new Error('Project image has conflicting or missing data');
        }
        urls.set(image.id, image.url);
    }
    const image = (reference: ImageReference) => {
        const url = urls.get(reference.mediaId);
        if (!url) throw new Error('Project image is unavailable');
        return url;
    };
    const copy = structuredClone(snapshot);
    const { customization } = copy;
    const { fit, comment, ...customizationFields } = customization;
    return {
        activeView: copy.activeView,
        canvasPixelSize: copy.canvasPixelSize,
        modelBounds: copy.modelBounds,
        customization: {
            ...customizationFields,
            ...(fit != null ? { fit } : {}),
            ...(comment != null ? { comment } : {}),
            modelImages: {
                front: image(customization.modelImages.front),
                back: image(customization.modelImages.back),
            },
            decorations: customization.decorations.map((item) => {
                const { text, categoryId, originalWidth, originalHeight, ...fields } = item;
                return {
                    ...fields,
                    image: image(item.image),
                    ...(text != null ? { text } : {}),
                    ...(categoryId != null ? { categoryId } : {}),
                    ...(originalWidth != null ? { originalWidth } : {}),
                    ...(originalHeight != null ? { originalHeight } : {}),
                };
            }),
        },
    };
}
