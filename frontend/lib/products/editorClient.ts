import { requestJson, requestReadJson } from '../api/http.ts';
import { bearerHeaders } from '../api/headers.ts';
import type { ProductDetail } from '../production/assortmentTypes.ts';
import {
    readPresetDetail,
    readEditorModel,
    readModelOptions,
    readFabricOptions,
    readSelectedFabrics,
    readSizeOptions,
} from './editorReads.ts';

export interface EditorModelOption {
    id: number;
    name: string;
    is_active: boolean;
}
export interface EditorModel extends EditorModelOption {
    sizes: EditorSize[];
}
export interface EditorSize {
    id: number;
    code: string;
    is_active: boolean;
}
export interface EditorFabric extends EditorModelOption {
    color_name: string;
    color_hex: string | null;
}
export interface EditorOptionPage<T> {
    items: T[];
    next_cursor: number | null;
}
export interface EditorQuery {
    query?: string;
    cursor?: string | null;
    limit?: number;
    model_id?: number;
}
export interface CatalogEditorClient {
    detail: (id: number, signal: AbortSignal) => Promise<ProductDetail>;
    models: (
        query: EditorQuery,
        signal: AbortSignal,
    ) => Promise<EditorOptionPage<EditorModelOption>>;
    model: (
        id: number,
        signal: AbortSignal,
        selectedSizeIds?: number[],
    ) => Promise<EditorModel>;
    sizes: (
        query: EditorQuery,
        signal: AbortSignal,
    ) => Promise<EditorOptionPage<EditorSize>>;
    fabrics: (
        query: EditorQuery,
        signal: AbortSignal,
    ) => Promise<EditorOptionPage<EditorFabric>>;
    selectedFabrics: (
        ids: number[],
        signal: AbortSignal,
    ) => Promise<EditorFabric[]>;
    save: (id: number, payload: unknown) => Promise<unknown>;
    upload: (file: File) => Promise<string>;
}
export function createCatalogEditorClient(config: {
    base: string;
    options: string;
    authorize: <T>(operation: (token: string) => Promise<T>) => Promise<T>;
    upload: (file: File) => Promise<string>;
}): CatalogEditorClient {
    const read = <T>(path: string, signal: AbortSignal) =>
        config.authorize((token) =>
            requestReadJson<T>(path, {
                signal,
                cache: 'no-store',
                headers: bearerHeaders(token),
            }),
        );
    const query = (value: EditorQuery) => {
        const params = new URLSearchParams();
        Object.entries(value).forEach(([key, item]) => {
            if (item != null && item !== '') params.set(key, String(item));
        });
        return params.toString();
    };
    return {
        detail: async (id, signal) =>
            readPresetDetail(
                await read(`${config.base}/products/${id}`, signal),
                id,
            ),
        models: async (parameters, signal) =>
            readModelOptions(
                await read(
                    `${config.options}/models?${query(parameters)}`,
                    signal,
                ),
                parameters,
            ),
        model: async (id, signal, selectedSizeIds = []) =>
            readEditorModel(
                await read(
                    `${config.options}/models/${id}?${new URLSearchParams(selectedSizeIds.map((id) => ['selected_size_ids', String(id)]))}`,
                    signal,
                ),
                id,
                selectedSizeIds,
            ),
        sizes: async (parameters, signal) =>
            readSizeOptions(
                await read(
                    `${config.options}/sizes?${query(parameters)}`,
                    signal,
                ),
                parameters,
            ),
        fabrics: async (parameters, signal) =>
            readFabricOptions(
                await read(
                    `${config.options}/fabrics?${query(parameters)}`,
                    signal,
                ),
                parameters,
            ),
        selectedFabrics: async (ids, signal) =>
            readSelectedFabrics(
                await read(
                    `${config.options}/selected-fabrics?${new URLSearchParams(ids.map((id) => ['ids', String(id)]))}`,
                    signal,
                ),
                ids,
            ),
        save: (id, payload) =>
            config.authorize((token) =>
                requestJson(`${config.base}/products${id ? `/${id}` : ''}`, {
                    method: id ? 'PUT' : 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        ...bearerHeaders(token),
                    },
                    body: JSON.stringify(payload),
                }),
            ),
        upload: config.upload,
    };
}
