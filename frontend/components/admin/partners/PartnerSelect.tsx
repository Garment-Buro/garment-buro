'use client';

import { useId, useState } from 'react';
import { useAdminPartnerDirectory } from '@/hooks/admin/useAdminPartnerDirectory';
import type { PartnerProfile } from '@/lib/partners/types';
import { inputClass } from './formStyles';

export function PartnerSelect({ value, revision, onChange }: { value: PartnerProfile | null; revision: number; onChange: (value: PartnerProfile | null) => void }) {
    const [query, setQuery] = useState('');
    const fieldId = useId();
    const page = useAdminPartnerDirectory({ query, selectable: true, limit: 24 }, revision);
    const known = new Map(page.items.map(partner => [partner.id, partner]));
    if (value) known.set(value.id, value);
    return <div className="min-w-0 sm:col-span-2 grid gap-2">
        <label htmlFor={`${fieldId}-search`} className="text-sm font-medium">Найти партнёра</label>
        <input id={`${fieldId}-search`} type="search" maxLength={100} className={inputClass} value={query} placeholder="Имя или код" onChange={event => setQuery(event.target.value)} />
        <label htmlFor={fieldId} className="text-sm font-medium">Партнёр</label>
        <select id={fieldId} required className={inputClass} value={value?.id ?? ''} onChange={event => onChange(known.get(Number(event.target.value)) ?? null)}>
            <option value="">Выберите партнёра</option>
            {[...known.values()].map(partner => <option key={partner.id} value={partner.id}>{partner.display_name} · {partner.code}</option>)}
        </select>
        {value && <p className="text-sm break-words" role="status">Выбран: {value.display_name} · {value.code}</p>}
        {page.loading && <p role="status">Загружаем партнёров…</p>}
        {page.message && <p role="alert">{page.message} <button type="button" onClick={() => void page.retry()}>Повторить</button></p>}
        {!page.loading && !page.message && page.items.length === 0 && <p>Партнёры не найдены.</p>}
        {page.hasMore && <button type="button" className="justify-self-start text-sm underline" disabled={page.loadingMore} onClick={() => void page.loadMore()}>{page.loadingMore ? 'Загрузка…' : 'Ещё партнёры'}</button>}
    </div>;
}
