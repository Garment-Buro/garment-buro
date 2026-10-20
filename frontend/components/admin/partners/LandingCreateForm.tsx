'use client';

import { useEffect, useState, type FormEvent } from 'react';

import { PartnerSelect } from './PartnerSelect';
import { AdminProductPicker } from './AdminProductPicker';
import type { PartnerLanding, PartnerLandingCreatePayload, PartnerProfile } from '@/lib/partners/types';

import { Field, inputClass } from './formStyles';

type LandingCreateFormProps = {
    partnersRevision: number;
    initialPartner?: PartnerProfile | null;
    createLanding: (partnerId: number, payload: PartnerLandingCreatePayload) => Promise<PartnerLanding>;
    onCreated: (landing: PartnerLanding) => void;
    onError: (message: string) => void;
};

const initialForm = {
    partner: null as PartnerProfile | null,
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
    partnersRevision,
    initialPartner,
    createLanding,
    onCreated,
    onError,
}: LandingCreateFormProps) => {
    const [saving, setSaving] = useState(false);
    const [form, setForm] = useState(initialForm);

    useEffect(() => {
        if (!initialPartner) return;
        setForm(current => ({ ...current, partner: initialPartner }));
    }, [initialPartner]);

    const submit = async (event: FormEvent) => {
        event.preventDefault();
        if (saving || !form.partner) return;
        setSaving(true);
        onError('');
        try {
            const landing = await createLanding(form.partner.id, {
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
            setForm(current => ({ ...initialForm, partner: current.partner }));
            onCreated(landing);
        } catch {
            onError('Не удалось сохранить лендинг. Проверьте адрес, изображения и обязательные поля.');
        } finally {
            setSaving(false);
        }
    };

    return (
        <form onSubmit={submit} className="rounded-xl border border-black/10 bg-white p-6">
            <fieldset disabled={saving} className="min-w-0">
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
                <PartnerSelect value={form.partner} revision={partnersRevision}
                    onChange={partner => setForm(current => ({ ...current, partner }))} />
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

            <AdminProductPicker ids={form.productIds} disabled={saving}
                onChange={productIds => setForm(current => ({ ...current, productIds }))} />

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

            <button disabled={saving || !form.partner} className="mt-6 h-11 rounded-lg bg-black px-5 text-sm font-semibold text-white disabled:opacity-40">
                {saving ? 'Сохраняем…' : form.status === 'published' ? 'Опубликовать лендинг' : 'Сохранить черновик'}
            </button>
            </fieldset>
        </form>
    );
};
