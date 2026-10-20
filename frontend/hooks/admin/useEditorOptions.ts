import { useCallback } from 'react';
import { usePagedCatalog } from '@/hooks/catalog/usePagedCatalog';
import type { EditorOptionPage, EditorQuery } from '@/lib/products/editorClient';

export function useEditorOptions<T extends { id: number }>(
    query: EditorQuery,
    load: (query: EditorQuery, signal: AbortSignal) => Promise<EditorOptionPage<T>>,
    active = true,
) {
    const request = useCallback(
        async (parameters: EditorQuery, signal: AbortSignal) => {
            const page = await load(parameters, signal);
            return {
                ...page,
                next_cursor: page.next_cursor === null ? null : String(page.next_cursor),
            };
        },
        [load],
    );
    const page = usePagedCatalog(query, JSON.stringify(query), request, active);
    return {
        ...page,
        loading: active && ['idle', 'loading'].includes(page.status),
        message: page.error instanceof Error ? page.error.message : '',
        hasMore: page.nextCursor !== null,
    };
}
