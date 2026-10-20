'use client';

import { useState } from 'react';
import { PageCursorExpiredError } from '@/lib/catalog/pagedResource';
import { useStorefrontProducts } from '@/hooks/catalog/useStorefrontProducts';
import { CollectionProductPicker } from '@/components/catalog/CollectionProductPicker';

export function PartnerProductPicker({ ids, disabled, onChange }: {
    ids: number[]; disabled: boolean; onChange: (ids: number[]) => void;
}) {
    const [query, setQuery] = useState('');
    const catalog = useStorefrontProducts({ query, limit: 24 });
    const selected = useStorefrontProducts({ ids, limit: 50 }, ids.length > 0);
    const known = new Map([...catalog.items, ...selected.items].map(item => [item.id, item]));
    return <CollectionProductPicker ids={ids} disabled={disabled} onChange={onChange}
        query={query} setQuery={setQuery} known={known}
        description="Здесь используются товары общего каталога."
        unavailableIds={selected.status === 'ready' ? ids.filter(id => !known.has(id)) : []}
        selectionError={Boolean(selected.error)} onRetrySelection={selected.retry}
        catalog={{ ...catalog, loading: catalog.status === 'loading' || catalog.status === 'idle',
            error: catalog.error instanceof Error ? catalog.error.message : Boolean(catalog.error),
            hasMore: catalog.nextCursor !== null && !(catalog.error instanceof PageCursorExpiredError) }} />;
}
