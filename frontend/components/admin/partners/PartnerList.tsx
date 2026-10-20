'use client';

import { useState } from 'react';
import { useAdminPartnerDirectory } from '@/hooks/admin/useAdminPartnerDirectory';
import type { PartnerProfile } from '@/lib/partners/types';
import { inputClass } from './formStyles';

const labels = { invited: 'Приглашён', active: 'Активен', suspended: 'Доступ приостановлен' };
export const PartnerList = ({ revision }: { revision: number }) => {
    const [query, setQuery] = useState('');
    const [status, setStatus] = useState<PartnerProfile['status'] | ''>('');
    const page = useAdminPartnerDirectory({query, status: status || undefined, limit:24}, revision);
    return <section className="mt-8 rounded-xl border border-black/10 bg-white p-6" aria-label="Справочник партнёров">
        <h2 className="text-lg font-semibold">Партнёры</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <label className="text-sm">Поиск партнёров<input type="search" maxLength={100} className={inputClass} value={query} onChange={event => setQuery(event.target.value)} /></label>
            <label className="text-sm">Статус партнёра<select className={inputClass} value={status} onChange={event => setStatus(event.target.value as typeof status)}><option value="">Все статусы</option>{Object.entries(labels).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        </div>
        {page.message && <p role="alert">{page.message} <button type="button" onClick={() => void page.retry()}>Обновить партнёров</button></p>}
        <div className="mt-5 divide-y divide-black/10">
            {page.loading ? <p role="status">Загрузка…</p> : page.items.map(partner => <article key={partner.id} className="grid gap-2 py-4 text-sm sm:grid-cols-[1fr_auto_auto] sm:items-center sm:gap-8">
                <div className="min-w-0 break-words"><p className="font-semibold">{partner.display_name}</p><p className="mt-1 text-black/45">{partner.code}</p></div>
                <p>{(partner.commission_bps / 100).toLocaleString('ru-RU')}%</p><p className="text-black/50">{labels[partner.status]}</p>
            </article>)}
            {!page.loading && !page.message && !page.items.length && <p className="py-8 text-sm text-black/50">Партнёры не найдены.</p>}
        </div>
        {page.hasMore && <button type="button" disabled={page.loadingMore} onClick={() => void page.loadMore()}>{page.loadingMore ? 'Загрузка…' : 'Ещё партнёры'}</button>}
    </section>;
};
