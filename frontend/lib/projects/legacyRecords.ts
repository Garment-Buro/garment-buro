import type {
    ConstructorCustomization,
    ConstructorDecoration,
    ConstructorDraftState,
    GarmentFit,
} from '../constructor/types.ts';
import type { ProjectKind } from './types.ts';

/** Historical browser record only. New projects are written through the account API. */
export type LegacyProjectRecord = {
    id: string;
    kind: ProjectKind;
    number: string;
    name: string;
    imageSrc: string;
    productId: number;
    savedAt: number;
    draftState?: ConstructorDraftState;
};

// These literal namespaces are retained for opening and explicit migration only.
export const LEGACY_CONSTRUCTOR_DRAFTS_STORAGE_KEY = 'plus2opacity-constructor-drafts';
export const LEGACY_COLLECTION_STORAGE_KEY = 'plus2opacity-my-collection';

const isRecord = (value: unknown): value is Record<string, unknown> => (
    Boolean(value) && typeof value === 'object'
);

const isFiniteNumber = (value: unknown): value is number => (
    typeof value === 'number' && Number.isFinite(value)
);

const isGarmentFit = (value: unknown): value is GarmentFit => {
    if (!isRecord(value)) return false;
    return (
        typeof value.selectedSize === 'string'
        && (value.sleeveMode === 'standard' || value.sleeveMode === 'height')
        && isFiniteNumber(value.lengthCm)
        && isFiniteNumber(value.widthCm)
        && isRecord(value.lengthRange)
        && isFiniteNumber(value.lengthRange.min)
        && isFiniteNumber(value.lengthRange.max)
        && isRecord(value.widthRange)
        && isFiniteNumber(value.widthRange.min)
        && isFiniteNumber(value.widthRange.max)
    );
};

const isConstructorDecoration = (value: unknown): value is ConstructorDecoration => {
    if (!isRecord(value)) return false;
    return (
        (value.view === 'front' || value.view === 'back')
        && typeof value.uid === 'string'
        && typeof value.variantId === 'string'
        && typeof value.name === 'string'
        && typeof value.image === 'string'
        && isFiniteNumber(value.price)
        && isFiniteNumber(value.widthCm)
        && isFiniteNumber(value.heightCm)
        && isFiniteNumber(value.x)
        && isFiniteNumber(value.y)
        && isFiniteNumber(value.scale)
        && isFiniteNumber(value.rotation)
    );
};

const isConstructorCustomization = (value: unknown): value is ConstructorCustomization => {
    if (!isRecord(value)) return false;
    return (
        value.kind === 'constructor'
        && typeof value.selectedSize === 'string'
        && isRecord(value.modelImages)
        && typeof value.modelImages.front === 'string'
        && typeof value.modelImages.back === 'string'
        && isRecord(value.canvas)
        && isFiniteNumber(value.canvas.widthCm)
        && isFiniteNumber(value.canvas.heightCm)
        && isRecord(value.garment)
        && isFiniteNumber(value.garment.widthCm)
        && isFiniteNumber(value.garment.heightCm)
        && (value.fit === undefined || isGarmentFit(value.fit))
        && Array.isArray(value.decorations)
        && value.decorations.every(isConstructorDecoration)
        && isFiniteNumber(value.totalPrice)
        && (value.comment === undefined || typeof value.comment === 'string')
    );
};

const isConstructorDraftState = (value: unknown): value is ConstructorDraftState => {
    if (!isRecord(value)) return false;
    return (
        (value.activeView === 'front' || value.activeView === 'back')
        && isRecord(value.canvasPixelSize)
        && isFiniteNumber(value.canvasPixelSize.width)
        && isFiniteNumber(value.canvasPixelSize.height)
        && isRecord(value.modelBounds)
        && isFiniteNumber(value.modelBounds.x)
        && isFiniteNumber(value.modelBounds.y)
        && isFiniteNumber(value.modelBounds.width)
        && isFiniteNumber(value.modelBounds.height)
        && isConstructorCustomization(value.customization)
    );
};

export const isLegacyProjectRecord = (value: unknown): value is LegacyProjectRecord => {
    if (!value || typeof value !== 'object') return false;
    const item = value as Partial<LegacyProjectRecord>;
    return (
        (item.kind === 'draft' || item.kind === 'collection')
        && typeof item.id === 'string'
        && typeof item.number === 'string'
        && typeof item.name === 'string'
        && typeof item.imageSrc === 'string'
        && typeof item.productId === 'number'
        && typeof item.savedAt === 'number'
        && (item.draftState === undefined || isConstructorDraftState(item.draftState))
    );
};

/** Read-only compatibility for an old constructor URL; never repair or rewrite its source. */
export const readLegacyConstructorDraft = (draftId: string | null | undefined): LegacyProjectRecord | undefined => {
    if (!draftId || typeof window === 'undefined') return undefined;
    try {
        const raw = window.localStorage.getItem(LEGACY_CONSTRUCTOR_DRAFTS_STORAGE_KEY);
        const parsed: unknown = raw ? JSON.parse(raw) : null;
        return Array.isArray(parsed)
            ? parsed.find((item): item is LegacyProjectRecord => isLegacyProjectRecord(item) && item.id === draftId)
            : undefined;
    } catch {
        // A denied storage getter/read or malformed historical data must not crash the editor.
        // The explicit migration screen reports storage issues without discarding records.
        return undefined;
    }
};
