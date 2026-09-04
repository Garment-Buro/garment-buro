import type { PartnerProfile } from '@/lib/partners/types';

export const PartnerList = ({ partners, loading }: { partners: PartnerProfile[]; loading: boolean }) => (
    <section className="mt-8 rounded-xl border border-black/10 bg-white p-6">
        <h2 className="text-lg font-semibold">Партнёры</h2>
        <div className="mt-5 divide-y divide-black/10">
            {loading ? <p className="py-8 text-sm text-black/50">Загрузка…</p> : partners.length ? partners.map(partner => (
                <div key={partner.id} className="grid gap-2 py-4 text-sm sm:grid-cols-[1fr_auto_auto] sm:items-center sm:gap-8">
                    <div><p className="font-semibold">{partner.display_name}</p><p className="mt-1 text-black/45">{partner.code}</p></div>
                    <p>{(partner.commission_bps / 100).toLocaleString('ru-RU')}%</p>
                    <p className="text-black/50">{partner.status}</p>
                </div>
            )) : <p className="py-8 text-sm text-black/50">Партнёров пока нет.</p>}
        </div>
    </section>
);
