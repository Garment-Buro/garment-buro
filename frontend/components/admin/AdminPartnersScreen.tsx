"use client";

import { useMemo, useState, type FormEvent } from 'react';

import { AdminPageShell } from '@/components/admin/AdminPageShell';
import { useAdminPartners } from '@/hooks/admin/useAdminPartners';

const inputClass = 'h-11 w-full rounded-lg border border-black/15 bg-white px-3 text-sm outline-none focus:border-black';

export const AdminPartnersScreen = () => {
    const { partners, loading, error, setError, addPartner, addLanding } = useAdminPartners();
    const [saving, setSaving] = useState(false);
    const [notice, setNotice] = useState('');
    const [partnerForm, setPartnerForm] = useState({
        email: '',
        code: '',
        display_name: '',
        commission_percent: '10',
    });
    const [landingForm, setLandingForm] = useState({
        partner_id: '',
        slug: '',
        title: '',
        eyebrow: '',
        headline: '',
        description: '',
        cta_label: 'Смотреть изделия',
        cta_href: '/',
        image_url: '',
        product_ids: '',
    });

    const activePartners = useMemo(
        () => partners.filter(partner => partner.status !== 'suspended'),
        [partners],
    );

    const submitPartner = async (event: FormEvent) => {
        event.preventDefault();
        setSaving(true);
        setError('');
        setNotice('');
        try {
            const created = await addPartner({
                email: partnerForm.email,
                code: partnerForm.code,
                display_name: partnerForm.display_name,
                commission_bps: Math.round(Number(partnerForm.commission_percent) * 100),
                status: 'active',
            });
            setPartnerForm({ email: '', code: '', display_name: '', commission_percent: '10' });
            setLandingForm(current => ({ ...current, partner_id: String(created.id) }));
            setNotice('Партнёр создан. Теперь добавьте для него лендинг.');
        } catch {
            setError('Не удалось создать партнёра. Проверьте почту и уникальный код.');
        } finally {
            setSaving(false);
        }
    };

    const submitLanding = async (event: FormEvent) => {
        event.preventDefault();
        setSaving(true);
        setError('');
        setNotice('');
        try {
            const productIds = landingForm.product_ids
                .split(',')
                .map(value => Number(value.trim()))
                .filter(value => Number.isInteger(value) && value > 0);
            await addLanding(Number(landingForm.partner_id), {
                slug: landingForm.slug,
                title: landingForm.title,
                eyebrow: landingForm.eyebrow || undefined,
                headline: landingForm.headline,
                description: landingForm.description,
                cta_label: landingForm.cta_label,
                cta_href: landingForm.cta_href,
                image_url: landingForm.image_url || undefined,
                product_ids: productIds,
                status: 'published',
            });
            setLandingForm(current => ({
                ...current,
                slug: '',
                title: '',
                eyebrow: '',
                headline: '',
                description: '',
                image_url: '',
                product_ids: '',
            }));
            setNotice('Лендинг опубликован. Ссылка готова к отправке блогеру.');
        } catch {
            setError('Не удалось опубликовать лендинг. Проверьте slug, ссылки и поля.');
        } finally {
            setSaving(false);
        }
    };

    return (
        <AdminPageShell activeSection="partners" title="Партнёрская программа">
            {error && <p className="mb-6 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
            {notice && <p className="mb-6 rounded-lg bg-green-50 px-4 py-3 text-sm text-green-800">{notice}</p>}

            <div className="grid gap-8 xl:grid-cols-2">
                <form onSubmit={submitPartner} className="rounded-xl border border-black/10 bg-white p-6">
                    <h2 className="text-lg font-semibold">Новый партнёр</h2>
                    <p className="mt-2 text-sm text-black/50">Доступ будет привязан к указанной почте.</p>
                    <div className="mt-6 grid gap-4 sm:grid-cols-2">
                        <Field label="Почта">
                            <input required type="email" className={inputClass} value={partnerForm.email} onChange={event => setPartnerForm(current => ({ ...current, email: event.target.value }))} />
                        </Field>
                        <Field label="Код партнёра">
                            <input required pattern="[a-z0-9][a-z0-9_-]+" className={inputClass} value={partnerForm.code} onChange={event => setPartnerForm(current => ({ ...current, code: event.target.value.toLowerCase() }))} placeholder="blogger_name" />
                        </Field>
                        <Field label="Имя для кабинета">
                            <input required className={inputClass} value={partnerForm.display_name} onChange={event => setPartnerForm(current => ({ ...current, display_name: event.target.value }))} />
                        </Field>
                        <Field label="Комиссия, %">
                            <input required type="number" min="0" max="100" step="0.01" className={inputClass} value={partnerForm.commission_percent} onChange={event => setPartnerForm(current => ({ ...current, commission_percent: event.target.value }))} />
                        </Field>
                    </div>
                    <button disabled={saving} className="mt-6 h-11 rounded-lg bg-black px-5 text-sm font-semibold text-white disabled:opacity-40">
                        Создать партнёра
                    </button>
                </form>

                <form onSubmit={submitLanding} className="rounded-xl border border-black/10 bg-white p-6">
                    <h2 className="text-lg font-semibold">Новый лендинг</h2>
                    <p className="mt-2 text-sm text-black/50">Публикуется по адресу garment-buro.ru/p/slug.</p>
                    <div className="mt-6 grid gap-4 sm:grid-cols-2">
                        <Field label="Партнёр">
                            <select required className={inputClass} value={landingForm.partner_id} onChange={event => setLandingForm(current => ({ ...current, partner_id: event.target.value }))}>
                                <option value="">Выберите партнёра</option>
                                {activePartners.map(partner => <option key={partner.id} value={partner.id}>{partner.display_name}</option>)}
                            </select>
                        </Field>
                        <Field label="Slug">
                            <input required pattern="[a-z0-9][a-z0-9-]+" className={inputClass} value={landingForm.slug} onChange={event => setLandingForm(current => ({ ...current, slug: event.target.value.toLowerCase() }))} placeholder="blogger-name" />
                        </Field>
                        <Field label="Название">
                            <input required className={inputClass} value={landingForm.title} onChange={event => setLandingForm(current => ({ ...current, title: event.target.value }))} />
                        </Field>
                        <Field label="Надзаголовок">
                            <input className={inputClass} value={landingForm.eyebrow} onChange={event => setLandingForm(current => ({ ...current, eyebrow: event.target.value }))} />
                        </Field>
                        <Field label="Главный заголовок" wide>
                            <input required className={inputClass} value={landingForm.headline} onChange={event => setLandingForm(current => ({ ...current, headline: event.target.value }))} />
                        </Field>
                        <Field label="Описание" wide>
                            <textarea required className="min-h-24 w-full rounded-lg border border-black/15 bg-white p-3 text-sm outline-none focus:border-black" value={landingForm.description} onChange={event => setLandingForm(current => ({ ...current, description: event.target.value }))} />
                        </Field>
                        <Field label="Текст кнопки">
                            <input required className={inputClass} value={landingForm.cta_label} onChange={event => setLandingForm(current => ({ ...current, cta_label: event.target.value }))} />
                        </Field>
                        <Field label="Ссылка кнопки">
                            <input required className={inputClass} value={landingForm.cta_href} onChange={event => setLandingForm(current => ({ ...current, cta_href: event.target.value }))} />
                        </Field>
                        <Field label="Ссылка на обложку" wide>
                            <input className={inputClass} value={landingForm.image_url} onChange={event => setLandingForm(current => ({ ...current, image_url: event.target.value }))} placeholder="https://… или /image.webp" />
                        </Field>
                        <Field label="ID товаров через запятую" wide>
                            <input className={inputClass} value={landingForm.product_ids} onChange={event => setLandingForm(current => ({ ...current, product_ids: event.target.value }))} placeholder="1, 2, 3" />
                        </Field>
                    </div>
                    <button disabled={saving || !partners.length} className="mt-6 h-11 rounded-lg bg-black px-5 text-sm font-semibold text-white disabled:opacity-40">
                        Опубликовать лендинг
                    </button>
                </form>
            </div>

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
        </AdminPageShell>
    );
};

const Field = ({ label, wide = false, children }: { label: string; wide?: boolean; children: React.ReactNode }) => (
    <label className={wide ? 'block sm:col-span-2' : 'block'}>
        <span className="mb-2 block text-sm font-medium text-black/70">{label}</span>
        {children}
    </label>
);
