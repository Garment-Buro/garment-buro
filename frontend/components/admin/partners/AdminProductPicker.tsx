'use client';

import { useState } from 'react';
import { CollectionProductPicker, type PickerProduct } from '@/components/catalog/CollectionProductPicker';
import { useIdentityCatalog } from '@/hooks/admin/useIdentityCatalog';

// This creation form has no existing server selection. Keep only chosen summaries,
// independent of the currently searched page; product IDs remain the saved value.
export function AdminProductPicker({ ids, disabled, onChange }: {
    ids: number[]; disabled: boolean; onChange: (ids: number[]) => void;
}) {
    const [query, setQuery] = useState('');
    const catalog = useIdentityCatalog({ query, sort: 'id:desc', limit: 24 });
    const [chosen, setChosen] = useState<Map<number, PickerProduct>>(new Map());
    const known = new Map([...chosen, ...catalog.items.map(item => [item.id, item] as const)]);
    const change = (next: number[]) => {
        if (next.length > 50) return;
        setChosen(new Map(next.flatMap(id => known.has(id) ? [[id, known.get(id)!] as const] : [])));
        onChange(next);
    };
    return <CollectionProductPicker ids={ids} disabled={disabled} onChange={change}
        query={query} setQuery={setQuery} known={known} catalog={catalog}
        description="Администратор также видит скрытые товары. Перед публикацией сервер проверит их доступность." />;
}
