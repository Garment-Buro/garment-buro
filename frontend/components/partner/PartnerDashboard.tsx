"use client";

import { useCallback, useEffect, useMemo, useState } from 'react';

import {
    createPartnerPayout,
    getPartnerCommissions,
    getPartnerDashboard,
    getPartnerLandings,
    getPartnerPayouts,
} from '@/lib/api/partners';
import { ApiError } from '@/lib/api/http';
import type {
    PartnerCommission,
    PartnerDashboard as PartnerDashboardData,
    PartnerLanding,
    PartnerPayout,
} from '@/lib/partners/types';
import { useAuthStore } from '@/store/authStore';

type Tab = 'overview' | 'links' | 'sales' | 'payouts';

const tabs: Array<{ id: Tab; label: string }> = [
    { id: 'overview', label: 'Обзор' },
    { id: 'links', label: 'Ссылки' },
    { id: 'sales', label: 'Продажи' },
    { id: 'payouts', label: 'Выплаты' },
];

const money = (value: string) => new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 2,
}).format(Number(value));

const date = (value: string) => new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
}).format(new Date(value));

const statusLabels: Record<PartnerPayout['status'], string> = {
    requested: 'На проверке',
    approved: 'Одобрена',
    paid: 'Выплачена',
    rejected: 'Отклонена',
    canceled: 'Отменена',
};

export const PartnerDashboard = () => {
    const { user, runAuthenticated, logout } = useAuthStore();
    const [tab, setTab] = useState<Tab>('overview');
    const [dashboard, setDashboard] = useState<PartnerDashboardData | null>(null);
    const [landings, setLandings] = useState<PartnerLanding[]>([]);
    const [commissions, setCommissions] = useState<PartnerCommission[]>([]);
    const [payouts, setPayouts] = useState<PartnerPayout[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [payoutAmount, setPayoutAmount] = useState('');
    const [payoutPending, setPayoutPending] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        setError('');
        const controller = new AbortController();
        try {
            const result = await runAuthenticated(token => Promise.all([
                getPartnerDashboard(token, controller.signal),
                getPartnerLandings(token, controller.signal),
                getPartnerCommissions(token, controller.signal),
                getPartnerPayouts(token, controller.signal),
            ]));
            setDashboard(result[0]);
            setLandings(result[1]);
            setCommissions(result[2]);
            setPayouts(result[3]);
        } catch (loadError) {
            setError(loadError instanceof ApiError && loadError.status === 403
                ? 'Для этого аккаунта не открыт партнёрский доступ.'
                : 'Не удалось загрузить кабинет. Попробуйте ещё раз.');
        } finally {
            setLoading(false);
        }
        return () => controller.abort();
    }, [runAuthenticated]);

    useEffect(() => {
        void load();
    }, [load]);

    const requestPayout = async () => {
        if (!payoutAmount || Number(payoutAmount) <= 0) return;
        setPayoutPending(true);
        setError('');
        try {
            await runAuthenticated(token => createPartnerPayout(token, payoutAmount));
            setPayoutAmount('');
            await load();
        } catch (requestError) {
            setError(requestError instanceof ApiError && requestError.status === 409
                ? 'Сумма больше доступного баланса.'
                : 'Не удалось создать заявку на выплату.');
        } finally {
            setPayoutPending(false);
        }
    };

    const metrics = useMemo(() => dashboard ? [
        { label: 'Переходы', value: dashboard.visits.toLocaleString('ru-RU') },
        { label: 'Заказы', value: dashboard.orders.toLocaleString('ru-RU') },
        { label: 'Конверсия', value: `${dashboard.conversion_percent}%` },
        { label: 'Начислено', value: money(dashboard.earned) },
    ] : [], [dashboard]);

    if (loading) {
        return <div className="flex min-h-dvh items-center justify-center text-sm text-black/50">Загружаем кабинет…</div>;
    }

    if (!dashboard) {
        return (
            <div className="mx-auto flex min-h-dvh max-w-xl flex-col items-center justify-center px-6 text-center">
                <p className="text-xl font-semibold text-black">Доступ пока не открыт</p>
                <p className="mt-3 text-sm leading-6 text-black/55">{error}</p>
                <button type="button" onClick={() => void logout()} className="mt-8 text-sm font-semibold underline">
                    Войти другим аккаунтом
                </button>
            </div>
        );
    }

    return (
        <div className="min-h-dvh bg-[#f4f4f0] text-black">
            <header className="border-b border-black/10 bg-[#f4f4f0]">
                <div className="mx-auto flex max-w-[1200px] items-center justify-between px-6 py-5 lg:px-8">
                    <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.18em]">GARMENT BURO</p>
                        <p className="mt-1 text-xs text-black/45">Партнёрский кабинет</p>
                    </div>
                    <div className="flex items-center gap-5 text-sm">
                        <span className="hidden text-black/55 sm:inline">{user?.email}</span>
                        <button type="button" onClick={() => void logout()} className="font-semibold hover:opacity-60">Выйти</button>
                    </div>
                </div>
            </header>

            <main className="mx-auto max-w-[1200px] px-6 py-10 lg:px-8 lg:py-16">
                <div className="flex flex-col justify-between gap-8 lg:flex-row lg:items-end">
                    <div>
                        <p className="text-sm text-black/45">Партнёр</p>
                        <h1 className="mt-2 text-3xl font-semibold tracking-[-0.04em] sm:text-4xl">
                            {dashboard.partner.display_name}
                        </h1>
                        <p className="mt-3 text-sm text-black/50">
                            Ваша ставка: {(dashboard.partner.commission_bps / 100).toLocaleString('ru-RU')}%
                        </p>
                    </div>
                    <div className="rounded-2xl bg-black px-6 py-5 text-white">
                        <p className="text-xs uppercase tracking-[0.16em] text-white/55">Доступно</p>
                        <p className="mt-2 text-3xl font-semibold tracking-[-0.04em]">{money(dashboard.available)}</p>
                    </div>
                </div>

                <nav className="mt-10 flex gap-1 overflow-x-auto border-b border-black/10" aria-label="Разделы кабинета">
                    {tabs.map(item => (
                        <button
                            key={item.id}
                            type="button"
                            onClick={() => setTab(item.id)}
                            className={`whitespace-nowrap border-b-2 px-4 py-3 text-sm font-medium transition ${tab === item.id ? 'border-black text-black' : 'border-transparent text-black/45 hover:text-black'}`}
                        >
                            {item.label}
                        </button>
                    ))}
                </nav>

                {error && <p className="mt-6 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}

                {tab === 'overview' && (
                    <section className="mt-8">
                        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                            {metrics.map(metric => (
                                <article key={metric.label} className="rounded-2xl border border-black/10 bg-white p-5">
                                    <p className="text-xs uppercase tracking-[0.12em] text-black/45">{metric.label}</p>
                                    <p className="mt-4 text-2xl font-semibold tracking-[-0.03em]">{metric.value}</p>
                                </article>
                            ))}
                        </div>
                        <div className="mt-6 grid gap-6 lg:grid-cols-[1.5fr_1fr]">
                            <article className="rounded-2xl border border-black/10 bg-white p-6">
                                <h2 className="text-lg font-semibold">Последние продажи</h2>
                                <CommissionList commissions={commissions.slice(0, 5)} />
                            </article>
                            <article className="rounded-2xl border border-black/10 bg-white p-6">
                                <h2 className="text-lg font-semibold">Баланс</h2>
                                <dl className="mt-6 space-y-4 text-sm">
                                    <BalanceRow label="Начислено" value={money(dashboard.earned)} />
                                    <BalanceRow label="Доступно" value={money(dashboard.available)} />
                                    <BalanceRow label="Выплачено" value={money(dashboard.paid)} />
                                </dl>
                            </article>
                        </div>
                    </section>
                )}

                {tab === 'links' && (
                    <section className="mt-8 space-y-4">
                        {landings.length ? landings.map(landing => (
                            <article key={landing.id} className="rounded-2xl border border-black/10 bg-white p-6">
                                <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-center">
                                    <div>
                                        <div className="flex items-center gap-3">
                                            <h2 className="font-semibold">{landing.title}</h2>
                                            <span className="rounded-full bg-black/5 px-2.5 py-1 text-xs text-black/55">{landing.status}</span>
                                        </div>
                                        <p className="mt-2 break-all text-sm text-black/50">garment-buro.ru/p/{landing.slug}</p>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => void navigator.clipboard.writeText(`https://garment-buro.ru/p/${landing.slug}`)}
                                        className="h-10 rounded-xl border border-black/15 px-4 text-sm font-semibold transition hover:bg-black hover:text-white"
                                    >
                                        Скопировать ссылку
                                    </button>
                                </div>
                            </article>
                        )) : <EmptyState text="Персональные ссылки появятся после публикации лендинга." />}
                    </section>
                )}

                {tab === 'sales' && (
                    <section className="mt-8 rounded-2xl border border-black/10 bg-white p-6">
                        <h2 className="text-lg font-semibold">Начисления по заказам</h2>
                        <CommissionList commissions={commissions} />
                    </section>
                )}

                {tab === 'payouts' && (
                    <section className="mt-8 grid gap-6 lg:grid-cols-[1fr_1.5fr]">
                        <article className="rounded-2xl border border-black/10 bg-white p-6">
                            <h2 className="text-lg font-semibold">Запросить выплату</h2>
                            <p className="mt-2 text-sm leading-6 text-black/50">Доступно: {money(dashboard.available)}</p>
                            <label className="mt-6 block">
                                <span className="mb-2 block text-sm font-medium">Сумма, ₽</span>
                                <input
                                    type="number"
                                    min="0.01"
                                    step="0.01"
                                    value={payoutAmount}
                                    onChange={event => setPayoutAmount(event.target.value)}
                                    className="h-12 w-full rounded-xl border border-black/15 px-4 outline-none focus:border-black focus:ring-2 focus:ring-black/10"
                                />
                            </label>
                            <button
                                type="button"
                                onClick={() => void requestPayout()}
                                disabled={payoutPending || !payoutAmount}
                                className="mt-4 h-12 w-full rounded-xl bg-black text-sm font-semibold text-white disabled:opacity-35"
                            >
                                {payoutPending ? 'Создаём заявку…' : 'Создать заявку'}
                            </button>
                        </article>
                        <article className="rounded-2xl border border-black/10 bg-white p-6">
                            <h2 className="text-lg font-semibold">История выплат</h2>
                            <div className="mt-5 divide-y divide-black/10">
                                {payouts.length ? payouts.map(payout => (
                                    <div key={payout.id} className="flex items-center justify-between gap-4 py-4 text-sm">
                                        <div>
                                            <p className="font-semibold">{money(payout.amount)}</p>
                                            <p className="mt-1 text-black/45">{date(payout.created_at)}</p>
                                        </div>
                                        <span className="text-right text-black/60">{statusLabels[payout.status]}</span>
                                    </div>
                                )) : <EmptyState text="Заявок на выплату пока нет." />}
                            </div>
                        </article>
                    </section>
                )}
            </main>
        </div>
    );
};

const BalanceRow = ({ label, value }: { label: string; value: string }) => (
    <div className="flex items-center justify-between border-b border-black/10 pb-4 last:border-0 last:pb-0">
        <dt className="text-black/50">{label}</dt>
        <dd className="font-semibold">{value}</dd>
    </div>
);

const CommissionList = ({ commissions }: { commissions: PartnerCommission[] }) => (
    <div className="mt-5 divide-y divide-black/10">
        {commissions.length ? commissions.map(commission => (
            <div key={commission.id} className="grid grid-cols-[1fr_auto] gap-4 py-4 text-sm sm:grid-cols-3">
                <span className="font-medium">Заказ №{commission.order_id}</span>
                <span className="hidden text-black/45 sm:inline">{date(commission.created_at)}</span>
                <span className="text-right font-semibold">+{money(commission.amount)}</span>
            </div>
        )) : <EmptyState text="Подтверждённых продаж пока нет." />}
    </div>
);

const EmptyState = ({ text }: { text: string }) => (
    <p className="py-10 text-center text-sm text-black/45">{text}</p>
);
