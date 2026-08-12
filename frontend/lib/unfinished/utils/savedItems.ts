import type {
    ConstructorCustomization,
    ConstructorDecoration,
    ConstructorDraftState,
    GarmentFit,
} from '@/lib/constructor/types';

export type SavedProfileItemKind = 'draft' | 'collection';

export type SavedProfileItem = {
    id: string;
    kind: SavedProfileItemKind;
    number: string;
    name: string;
    imageSrc: string;
    productId: number;
    savedAt: number;
    draftState?: ConstructorDraftState;
};

export type SavedProfileItemInput = {
    kind: SavedProfileItemKind;
    index: number;
    productId: number;
    title: string;
    imageSrc: string;
    savedAt?: number;
    draftState?: ConstructorDraftState;
};

export const CONSTRUCTOR_DRAFTS_STORAGE_KEY = 'plus2opacity-constructor-drafts';
export const MY_COLLECTION_STORAGE_KEY = 'plus2opacity-my-collection';

const FALLBACK_IMAGE_SRC = '/mock/hoodie.webp';

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

const isSavedProfileItem = (value: unknown): value is SavedProfileItem => {
    if (!value || typeof value !== 'object') return false;
    const item = value as Partial<SavedProfileItem>;
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

export const buildSavedProfileItem = ({
    kind,
    index,
    productId,
    title,
    imageSrc,
    savedAt = Date.now(),
    draftState,
}: SavedProfileItemInput): SavedProfileItem => ({
    id: `${kind}-${savedAt}-${productId}`,
    kind,
    number: String(index + 1).padStart(3, '0'),
    name: title.trim() || 'custom garment',
    imageSrc: imageSrc.trim() || FALLBACK_IMAGE_SRC,
    productId,
    savedAt,
    ...(draftState ? { draftState } : {}),
});

export const parseSavedProfileItems = (value: string | null | undefined): SavedProfileItem[] => {
    if (!value) return [];
    try {
        const parsed = JSON.parse(value) as unknown;
        return Array.isArray(parsed) ? parsed.filter(isSavedProfileItem) : [];
    } catch {
        return [];
    }
};

export const serializeSavedProfileItems = (items: SavedProfileItem[]) => JSON.stringify(items);

export const loadSavedProfileItems = (storageKey: string): SavedProfileItem[] => {
    if (typeof window === 'undefined') return [];
    return parseSavedProfileItems(window.localStorage.getItem(storageKey));
};

export const saveSavedProfileItems = (storageKey: string, items: SavedProfileItem[]) => {
    if (typeof window !== 'undefined') {
        window.localStorage.setItem(storageKey, serializeSavedProfileItems(items));
    }
};

export const saveConstructorDraft = ({
    draftId,
    productId,
    title,
    imageSrc,
    draftState,
}: {
    draftId?: string | null;
    productId: number;
    title: string;
    imageSrc: string;
    draftState?: ConstructorDraftState;
}) => {
    const existingItems = loadSavedProfileItems(CONSTRUCTOR_DRAFTS_STORAGE_KEY);
    const existingItem = draftId ? existingItems.find((item) => item.id === draftId) : undefined;
    const builtItem = buildSavedProfileItem({
        kind: 'draft',
        index: existingItems.length,
        productId,
        title,
        imageSrc,
        draftState,
    });
    const nextItem = existingItem
        ? { ...builtItem, id: existingItem.id, number: existingItem.number }
        : builtItem;
    saveSavedProfileItems(CONSTRUCTOR_DRAFTS_STORAGE_KEY, [
        nextItem,
        ...existingItems.filter((item) => item.id !== existingItem?.id),
    ]);
    return nextItem;
};

export const loadConstructorDraft = (draftId: string | null | undefined) => {
    if (!draftId) return undefined;
    return loadSavedProfileItems(CONSTRUCTOR_DRAFTS_STORAGE_KEY).find((item) => item.id === draftId);
};

export const removeSavedProfileItem = (storageKey: string, itemId: string) => {
    const nextItems = loadSavedProfileItems(storageKey).filter(item => item.id !== itemId);
    saveSavedProfileItems(storageKey, nextItems);
    return nextItems;
};
