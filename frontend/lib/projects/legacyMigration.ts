import { readLocalRasterImage } from '../api/http.ts';
import {
    LEGACY_CONSTRUCTOR_DRAFTS_STORAGE_KEY,
    LEGACY_COLLECTION_STORAGE_KEY,
    isLegacyProjectRecord,
    type LegacyProjectRecord,
} from './legacyRecords.ts';
import { PROJECT_IMAGE_MAX_BYTES } from './images.ts';
import { serializeProjectSnapshot } from './snapshot.ts';
import type { ImageReference, ProjectCreate, ProjectSummary } from './types.ts';

const storageKeys = [LEGACY_CONSTRUCTOR_DRAFTS_STORAGE_KEY, LEGACY_COLLECTION_STORAGE_KEY];
type SourceStorage = Pick<Storage, 'getItem'>;
export type LegacyProjectEntry = {
    key: string;
    storageKey: string;
    serializedRecord: string;
    item: LegacyProjectRecord;
};
export type LegacyProjectScan = {
    entries: LegacyProjectEntry[];
    issues: Array<{ key: string; title: string; reason: string }>;
};
export type LegacyMigrationTransport = {
    receipt: (key: string, signal: AbortSignal) => Promise<ProjectSummary | null>;
    product: (id: number, signal: AbortSignal) => Promise<{ id: number; media_assets?: Array<{ id: number; url: string }> }>;
    upload: (image: Blob, signal?: AbortSignal) => Promise<{ id: number }>;
    create: (payload: ProjectCreate, signal: AbortSignal) => Promise<ProjectSummary>;
};
type MigrationOptions = {
    storage: SourceStorage;
    transport: LegacyMigrationTransport;
    origin: string;
    signal: AbortSignal;
    assertCurrent: () => void;
};

/** Locate array members in validated JSON, retaining their original number and string tokens. */
function rawRecords(raw: string): string[] {
    if (!Array.isArray(JSON.parse(raw))) throw new Error('Not an array');
    const records: string[] = [];
    let start = raw.indexOf('[') + 1, depth = 1, inString = false, escaped = false;
    for (let index = start; index < raw.length; index++) {
        const char = raw[index];
        if (inString) {
            if (escaped) escaped = false;
            else if (char === '\\') escaped = true;
            else if (char === '"') inString = false;
            continue;
        }
        if (char === '"') inString = true;
        else if (char === '[' || char === '{') depth++;
        else if (char === ']' || char === '}') {
            depth--;
            if (depth === 0) {
                const last = raw.slice(start, index).trim();
                if (last) records.push(last);
                return records;
            }
        } else if (char === ',' && depth === 1) {
            records.push(raw.slice(start, index).trim());
            start = index + 1;
        }
    }
    throw new Error('Invalid JSON array');
}

/** Lossless inspection: unsupported rows are reported, never rewritten or discarded. */
export function scanLegacyProjects(storage: SourceStorage): LegacyProjectScan {
    const result: LegacyProjectScan = { entries: [], issues: [] };
    for (const storageKey of storageKeys) {
        try {
            const raw = storage.getItem(storageKey);
            if (raw === null) continue;
            rawRecords(raw).forEach((serializedRecord, index) => {
                const value: unknown = JSON.parse(serializedRecord);
                const key = `${storageKey}:${index}`;
                const item = isLegacyProjectRecord(value) ? value : null;
                const title = item?.name || `Локальная запись ${index + 1}`;
                const reason = !item ? 'Формат записи не распознан. Исходные данные сохранены.'
                    : !item.draftState ? 'Нет полного состояния редактора. Автоматический перенос невозможен.'
                        : !Number.isInteger(item.productId) || item.productId <= 0 || item.productId > 2_147_483_647
                            ? 'Нет постоянного идентификатора товара.'
                            : !item.name.trim() || item.name.trim().length > 200 ? 'Название проекта должно содержать от 1 до 200 символов.' : null;
                if (reason || !item) result.issues.push({ key, title, reason: reason! });
                else result.entries.push({ key, storageKey, serializedRecord, item });
            });
        } catch {
            result.issues.push({ key: storageKey, title: storageKey === LEGACY_CONSTRUCTOR_DRAFTS_STORAGE_KEY ? 'Старые черновики' : 'Старая коллекция', reason: 'Не удалось прочитать локальные записи. Исходные данные сохранены.' });
        }
    }
    return result;
}

export async function legacyProjectKey(entry: LegacyProjectEntry) {
    // Well-formed JSON escapes lone UTF-16 surrogates before UTF-8 encoding;
    // TextEncoder alone would collapse different source strings into U+FFFD.
    const bytes = new TextEncoder().encode(JSON.stringify([entry.storageKey, entry.serializedRecord]));
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    return 'legacy-v1-' + Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
}

function check(options: MigrationOptions) {
    options.signal.throwIfAborted();
    options.assertCurrent();
}

function sourceRecords(entry: LegacyProjectEntry, storage: SourceStorage): string[] {
    if (!storageKeys.includes(entry.storageKey)) throw new Error('Неизвестное хранилище проектов.');
    return rawRecords(storage.getItem(entry.storageKey) ?? '[]');
}

function unchanged(entry: LegacyProjectEntry, storage: SourceStorage) {
    return sourceRecords(entry, storage).includes(entry.serializedRecord);
}

/** Stable key is scoped by the server account, including after reload or a lost POST response. */
export async function importLegacyProject(entry: LegacyProjectEntry, options: MigrationOptions): Promise<ProjectSummary> {
    check(options);
    const original: unknown = JSON.parse(entry.serializedRecord);
    if (!isLegacyProjectRecord(original) || !original.draftState || !unchanged(entry, options.storage)) {
        throw new Error('Локальная запись изменилась. Обновите список перед переносом.');
    }
    const key = await legacyProjectKey(entry);
    check(options);
    const existing = await options.transport.receipt(key, options.signal);
    check(options);
    if (existing) return existing;
    const product = await options.transport.product(original.productId, options.signal);
    check(options);
    if (product.id !== original.productId) throw new Error('Не удалось подтвердить исходный товар.');
    const references = new Map<string, ImageReference>((product.media_assets ?? []).map(asset => [asset.url, { mediaId: asset.id }]));
    const { customization } = original.draftState;
    const sources = new Set([customization.modelImages.front, customization.modelImages.back, ...customization.decorations.map(item => item.image)]);
    // Read every new image before uploading any: arbitrary and stale URLs cannot cause partial imports.
    const images = new Map<string, Blob>();
    for (const source of sources) {
        check(options);
        if (!references.has(source)) images.set(source, await readLocalRasterImage(source, {
            origin: options.origin, maxBytes: PROJECT_IMAGE_MAX_BYTES, signal: options.signal,
        }));
    }
    const snapshot = await serializeProjectSnapshot(original.draftState, async source => {
        check(options);
        const known = references.get(source);
        if (known) return known;
        const image = images.get(source);
        if (!image) throw new Error('Не удалось прочитать изображение проекта.');
        const uploaded = await options.transport.upload(image, options.signal);
        check(options);
        return { mediaId: uploaded.id };
    }, options.signal);
    check(options);
    if (!unchanged(entry, options.storage)) throw new Error('Локальная запись изменилась во время переноса. Обновите список.');
    try {
        const saved = await options.transport.create({
            client_key: key, product_id: original.productId, kind: original.kind,
            title: original.name.trim(), snapshot,
        }, options.signal);
        check(options);
        return saved;
    } catch (error) {
        check(options);
        if (error && typeof error === 'object' && 'status' in error && error.status === 409) {
            const receipt = await options.transport.receipt(key, options.signal);
            check(options);
            if (receipt) return receipt;
        }
        throw error;
    }
}

/** Called only by an explicit cleanup action, under the browser's shared migration lock. */
export async function removeImportedLegacyProject(
    entry: LegacyProjectEntry, projectId: number,
    options: MigrationOptions & { storage: Pick<Storage, 'getItem' | 'setItem'> },
) {
    check(options);
    const key = await legacyProjectKey(entry);
    check(options);
    const receipt = await options.transport.receipt(key, options.signal);
    check(options);
    if (!receipt || receipt.id !== projectId) throw new Error('Сохранение в этом аккаунте не подтверждено. Локальная копия сохранена.');
    const values = sourceRecords(entry, options.storage);
    const index = values.indexOf(entry.serializedRecord);
    if (index < 0) return false;
    values.splice(index, 1);
    // No await between reading, account guard and writing; preserve every unknown row.
    check(options);
    options.storage.setItem(entry.storageKey, `[${values.join(',')}]`);
    return true;
}
