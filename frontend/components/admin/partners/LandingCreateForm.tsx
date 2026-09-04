'use client';

import { useEffect, useState, type FormEvent } from 'react';

import { useAdminProducts } from '@/hooks/admin/useAdminProducts';
import type { PartnerLanding, PartnerLandingCreatePayload, PartnerProfile } from '@/lib/partners/types';

import { Field, inputClass } from './formStyles';

type LandingCreateFormProps = {
    partners: PartnerProfile[];
    initialPartnerId?: number;
    createLanding: (partnerId: number, payload: PartnerLandingCreatePayload) => Promise<PartnerLanding>;
    onCreated: (landing: PartnerLanding) => void;
    onError: (message: string) => void;
};

const initialForm = {
    partnerId: '',
    slug: '',
    title: '',
    eyebrow: '',
    headline: '',
    description: '',
    ctaLabel: 'Выбрать модель',
    imageUrl: '',
    logoUrl: '',
    secondaryImageUrl: '',
    storyTitle: '',
    storyBody: '',
    modelHeading: '',
    proofLine: '',
    finalHeading: '',
    status: 'draft' as 'draft' | 'published',
    productIds: [] as number[],
};

export const LandingCreateForm = ({
    partners,
    initialPartnerId,
    createLanding,
    onCreated,
    onError,
}: LandingCreateFormProps) => {
    const { products, isLoading } = useAdminProducts();
    const [saving, setSaving] = useState(false);
    const [form, setForm] = useState(initialForm);

    useEffect(() => {
        if (!initialPartnerId) return;
        setForm(current => ({ ...current, partnerId: String(initialPartnerId) }));
    }, [initialPartnerId]);

    const toggleProduct = (productId: number) => {
        setForm(current => ({
            ...current,
            productIds: current.productIds.includes(productId)
                ? current.productIds.filter(id => id !== productId)
                : [...current.productIds, productId],
        }));
    };

    const submit = async (event: FormEvent) => {
        event.preventDefault();
        setSaving(true);
        onError('');
        try {
            const landing = await createLanding(Number(form.partnerId), {
                slug: form.slug,
                title: form.title,
                eyebrow: form.eyebrow || undefined,
                headline: form.headline,
                description: form.description,
                cta_label: form.ctaLabel,
                cta_href: '/constructor',
                image_url: form.imageUrl || undefined,
                template_key: 'light-running',
                content: {
                    logo_url: form.logoUrl || undefined,
                    secondary_image_url: form.secondaryImageUrl || undefined,
                    story_title: form.storyTitle || undefined,
                    story_body: form.storyBody || undefined,
                    model_heading: form.modelHeading || undefined,
                    proof_line: form.proofLine || undefined,
                    final_heading: form.finalHeading || undefined,
                    faq: [],
                },
                product_ids: form.productIds,
                status: form.status,
            });
            setForm(current => ({ ...initialForm, partnerId: current.partnerId }));
            onCreated(landing);
        } catch {
            onError('Не удалось сохранить лендинг. Проверьте адрес, изображения и обязательные поля.');
        } finally {
            setSaving(false);
        }
    };

    return (
        <form onSubmit={submit} className="rounded-xl border border-black/10 bg-white p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <h2 className="text-lg font-semibold">Новый лендинг</h2>
                    <p className="mt-2 text-sm text-black/50">Шаблон повторяет композицию LightRunning и наполняется данными коллекции.</p>
                </div>
                <select className={inputClass} value={form.status} onChange={event => setForm(current => ({ ...current, status: event.target.value as 'draft' | 'published' }))} aria-label="Статус лендинга">
                    <option value="draft">Сохранить черновик</option>
                    <option value="published">Опубликовать</option>
                </select>
            </div>

            <div className="mt-6 grid gap-4 sm:grid-cols-2">
                <Field label="Партнёр">
                    <select required className={inputClass} value={form.partnerId} onChange={event => setForm(current => ({ ...current, partnerId: event.target.value }))}>
                        <option value="">Выберите партнёра</option>
                        {partners.map(partner => <option key={partner.id} value={partner.id}>{partner.display_name}</option>)}
                    </select>
                </Field>
                <Field label="Адрес страницы">
                    <input required pattern="[a-z0-9][a-z0-9-]+" className={inputClass} value={form.slug} onChange={event => setForm(current => ({ ...current, slug: event.target.value.toLowerCase() }))} placeholder="author-collection" />
                </Field>
                <Field label="SEO название">
                    <input required className={inputClass} value={form.title} onChange={event => setForm(current => ({ ...current, title: event.target.value }))} />
                </Field>
                <Field label="Надзаголовок">
                    <input className={inputClass} value={form.eyebrow} onChange={event => setForm(current => ({ ...current, eyebrow: event.target.value }))} placeholder="Автор × GARMENT BURO" />
                </Field>
                <Field label="Главный заголовок" wide>
                    <input required className={inputClass} value={form.headline} onChange={event => setForm(current => ({ ...current, headline: event.target.value }))} />
                </Field>
                <Field label="Описание" wide>
                    <textarea required className="min-h-24 w-full rounded-lg border border-black/15 bg-white p-3 text-sm outline-none transition focus:border-black focus:ring-2 focus:ring-black/10" value={form.description} onChange={event => setForm(current => ({ ...current, description: event.target.value }))} />
                </Field>
                <Field label="Текст кнопки">
                    <input required className={inputClass} value={form.ctaLabel} onChange={event => setForm(current => ({ ...current, ctaLabel: event.target.value }))} />
                </Field>
                <Field label="Главное изображение">
                    <input className={inputClass} value={form.imageUrl} onChange={event => setForm(current => ({ ...current, imageUrl: event.target.value }))} placeholder="https://… или /image.webp" />
                </Field>
            </div>

            <fieldset className="mt-6">
                <legend className="text-sm font-semibold">Модели коллекции</legend>
                <p className="mt-1 text-sm text-black/50">Покупатель увидит их крупными блоками и перейдёт сразу в конструктор.</p>
                <div className="mt-4 grid gap-2 sm:grid-cols-2">
                    {isLoading ? <p className="text-sm text-black/50">Загружаем модели…</p> : products.map(product => (
                        <label key={product.id} className="flex cursor-pointer items-center justify-between gap-4 rounded-lg border border-black/10 p-3 text-sm transition hover:bg-black/[.03]">
                            <span><span className="font-semibold">{product.title}</span><span className="ml-2 text-black/40">#{product.id}</span></span>
                            <input type="checkbox" checked={form.productIds.includes(product.id)} onChange={() => toggleProduct(product.id)} className="size-4 accent-black" />
                        </label>
                    ))}
                </div>
            </fieldset>

            <details className="mt-6 rounded-lg border border-black/10 p-4">
                <summary className="cursor-pointer text-sm font-semibold">Дополнительный контент</summary>
                <div className="mt-5 grid gap-4 sm:grid-cols-2">
                    <Field label="Логотип партнёра"><input className={inputClass} value={form.logoUrl} onChange={event => setForm(current => ({ ...current, logoUrl: event.target.value }))} /></Field>
                    <Field label="Второе изображение"><input className={inputClass} value={form.secondaryImageUrl} onChange={event => setForm(current => ({ ...current, secondaryImageUrl: event.target.value }))} /></Field>
                    <Field label="Заголовок истории" wide><input className={inputClass} value={form.storyTitle} onChange={event => setForm(current => ({ ...current, storyTitle: event.target.value }))} /></Field>
                    <Field label="История коллекции" wide><textarea className="min-h-24 w-full rounded-lg border border-black/15 p-3 text-sm" value={form.storyBody} onChange={event => setForm(current => ({ ...current, storyBody: event.target.value }))} /></Field>
                    <Field label="Заголовок моделей"><input className={inputClass} value={form.modelHeading} onChange={event => setForm(current => ({ ...current, modelHeading: event.target.value }))} /></Field>
                    <Field label="Строка доверия"><input className={inputClass} value={form.proofLine} onChange={event => setForm(current => ({ ...current, proofLine: event.target.value }))} /></Field>
                    <Field label="Финальный призыв" wide><input className={inputClass} value={form.finalHeading} onChange={event => setForm(current => ({ ...current, finalHeading: event.target.value }))} /></Field>
                </div>
            </details>

            <button disabled={saving || !partners.length} className="mt-6 h-11 rounded-lg bg-black px-5 text-sm font-semibold text-white disabled:opacity-40">
                {saving ? 'Сохраняем…' : form.status === 'published' ? 'Опубликовать лендинг' : 'Сохранить черновик'}
            </button>
        </form>
    );
};
