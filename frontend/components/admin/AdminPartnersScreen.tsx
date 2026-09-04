'use client';

import { useMemo, useState } from 'react';

import { AdminPageShell } from '@/components/admin/AdminPageShell';
import { LandingCreateForm } from '@/components/admin/partners/LandingCreateForm';
import { LandingList } from '@/components/admin/partners/LandingList';
import { PartnerCreateForm } from '@/components/admin/partners/PartnerCreateForm';
import { PartnerList } from '@/components/admin/partners/PartnerList';
import { useAdminPartners } from '@/hooks/admin/useAdminPartners';

export const AdminPartnersScreen = () => {
    const {
        partners,
        landings,
        loading,
        error,
        setError,
        addPartner,
        addLanding,
        updateLanding,
    } = useAdminPartners();
    const [notice, setNotice] = useState('');
    const [selectedPartnerId, setSelectedPartnerId] = useState<number>();
    const activePartners = useMemo(
        () => partners.filter(partner => partner.status !== 'suspended'),
        [partners],
    );

    return (
        <AdminPageShell activeSection="partners" title="Партнёры и лендинги">
            <div className="mb-8 rounded-xl bg-black p-6 text-white">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-white/50">Новый основной сценарий</p>
                <p className="mt-3 max-w-3xl text-lg leading-7">
                    Партнёр получает отдельный лендинг. Вы выбираете модели, покупатель открывает конструктор,
                    а заказ и комиссия связываются с автором коллекции.
                </p>
            </div>

            {error && <p className="mb-6 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
            {notice && <p className="mb-6 rounded-lg bg-green-50 px-4 py-3 text-sm text-green-800">{notice}</p>}

            <div className="grid gap-8 xl:grid-cols-[.75fr_1.25fr]">
                <PartnerCreateForm
                    createPartner={addPartner}
                    onCreated={partner => {
                        setSelectedPartnerId(partner.id);
                        setNotice('Партнёр создан. Теперь соберите для него лендинг.');
                    }}
                    onError={setError}
                />
                <LandingCreateForm
                    partners={activePartners}
                    initialPartnerId={selectedPartnerId}
                    createLanding={addLanding}
                    onCreated={landing => setNotice(
                        landing.status === 'published'
                            ? 'Лендинг опубликован и готов к отправке партнёру.'
                            : 'Черновик лендинга сохранён.',
                    )}
                    onError={setError}
                />
            </div>

            <LandingList
                landings={landings}
                partners={partners}
                loading={loading}
                updateLanding={updateLanding}
                onError={setError}
            />
            <PartnerList partners={partners} loading={loading} />
        </AdminPageShell>
    );
};
