'use client';

import { useState, type FormEvent } from 'react';

import type { PartnerCreatePayload, PartnerProfile } from '@/lib/partners/types';

import { Field, inputClass } from './formStyles';

type PartnerCreateFormProps = {
    createPartner: (payload: PartnerCreatePayload) => Promise<PartnerProfile>;
    onCreated: (partner: PartnerProfile) => void;
    onError: (message: string) => void;
};

export const PartnerCreateForm = ({ createPartner, onCreated, onError }: PartnerCreateFormProps) => {
    const [saving, setSaving] = useState(false);
    const [form, setForm] = useState({ email: '', code: '', displayName: '', commissionPercent: '10' });

    const submit = async (event: FormEvent) => {
        event.preventDefault();
        setSaving(true);
        onError('');
        try {
            const partner = await createPartner({
                email: form.email,
                code: form.code,
                display_name: form.displayName,
                commission_bps: Math.round(Number(form.commissionPercent) * 100),
                status: 'active',
            });
            setForm({ email: '', code: '', displayName: '', commissionPercent: '10' });
            onCreated(partner);
        } catch {
            onError('Не удалось создать партнёра. Проверьте почту и уникальный код.');
        } finally {
            setSaving(false);
        }
    };

    return (
        <form onSubmit={submit} className="rounded-xl border border-black/10 bg-white p-6">
            <h2 className="text-lg font-semibold">Новый партнёр</h2>
            <p className="mt-2 text-sm text-black/50">Кабинет будет привязан к указанной почте.</p>
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
                <Field label="Почта">
                    <input required type="email" className={inputClass} value={form.email} onChange={event => setForm(current => ({ ...current, email: event.target.value }))} />
                </Field>
                <Field label="Код партнёра">
                    <input required pattern="[a-z0-9][a-z0-9_-]+" className={inputClass} value={form.code} onChange={event => setForm(current => ({ ...current, code: event.target.value.toLowerCase() }))} placeholder="blogger_name" />
                </Field>
                <Field label="Имя для кабинета">
                    <input required className={inputClass} value={form.displayName} onChange={event => setForm(current => ({ ...current, displayName: event.target.value }))} />
                </Field>
                <Field label="Комиссия, %">
                    <input required type="number" min="0" max="100" step="0.01" className={inputClass} value={form.commissionPercent} onChange={event => setForm(current => ({ ...current, commissionPercent: event.target.value }))} />
                </Field>
            </div>
            <button disabled={saving} className="mt-6 h-11 rounded-lg bg-black px-5 text-sm font-semibold text-white disabled:opacity-40">
                {saving ? 'Создаём…' : 'Создать партнёра'}
            </button>
        </form>
    );
};
