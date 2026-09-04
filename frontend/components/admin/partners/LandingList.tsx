'use client';

import Link from 'next/link';
import { useState } from 'react';

import type { PartnerLanding, PartnerLandingUpdatePayload, PartnerProfile } from '@/lib/partners/types';

type LandingListProps = {
    landings: PartnerLanding[];
    partners: PartnerProfile[];
    loading: boolean;
    updateLanding: (landingId: number, payload: PartnerLandingUpdatePayload) => Promise<PartnerLanding>;
    onError: (message: string) => void;
};

const statusLabel = {
    draft: 'Черновик',
    published: 'Опубликован',
    archived: 'В архиве',
};

export const LandingList = ({ landings, partners, loading, updateLanding, onError }: LandingListProps) => {
    const [pendingId, setPendingId] = useState<number | null>(null);
    const partnerNames = new Map(partners.map(partner => [partner.id, partner.display_name]));

    const togglePublished = async (landing: PartnerLanding) => {
        setPendingId(landing.id);
        onError('');
        try {
            await updateLanding(landing.id, {
                status: landing.status === 'published' ? 'draft' : 'published',
            });
        } catch {
            onError('Не удалось изменить статус лендинга.');
        } finally {
            setPendingId(null);
        }
    };

    return (
        <section className="mt-8 rounded-xl border border-black/10 bg-white p-6">
            <div className="flex items-end justify-between gap-4">
                <div>
                    <h2 className="text-lg font-semibold">Лендинги</h2>
                    <p className="mt-1 text-sm text-black/50">Все страницы коллекций и их текущий статус.</p>
                </div>
                <span className="text-sm text-black/40">{landings.length}</span>
            </div>
            <div className="mt-5 divide-y divide-black/10">
                {loading ? <p className="py-8 text-sm text-black/50">Загрузка…</p> : landings.length ? landings.map(landing => (
                    <article key={landing.id} className="grid gap-4 py-5 lg:grid-cols-[1fr_auto_auto] lg:items-center">
                        <div>
                            <div className="flex flex-wrap items-center gap-3">
                                <h3 className="font-semibold">{landing.title}</h3>
                                <span className="rounded-full bg-black/5 px-3 py-1 text-xs text-black/55">{statusLabel[landing.status]}</span>
                            </div>
                            <p className="mt-2 text-sm text-black/45">{partnerNames.get(landing.partner_id) || 'Партнёр'} · /p/{landing.slug}</p>
                            <p className="mt-1 text-xs text-black/35">Моделей: {landing.product_ids.length}</p>
                        </div>
                        {landing.status === 'published' ? (
                            <Link href={`/p/${landing.slug}`} target="_blank" className="text-sm font-semibold underline underline-offset-4">Открыть</Link>
                        ) : <span className="text-sm text-black/35">Предпросмотр после публикации</span>}
                        <button
                            type="button"
                            disabled={pendingId === landing.id || landing.status === 'archived'}
                            onClick={() => void togglePublished(landing)}
                            className="h-10 rounded-lg border border-black/15 px-4 text-sm font-semibold transition hover:bg-black hover:text-white disabled:opacity-35"
                        >
                            {pendingId === landing.id ? 'Сохраняем…' : landing.status === 'published' ? 'Снять с публикации' : 'Опубликовать'}
                        </button>
                    </article>
                )) : <p className="py-8 text-sm text-black/50">Создайте первый лендинг коллекции.</p>}
            </div>
        </section>
    );
};
