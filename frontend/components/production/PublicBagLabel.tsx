'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { requestJson } from '@/lib/api/http';
import { stateLabels } from '@/lib/production/types';
import styles from './ProductionTerminal.module.css';

interface Label {
    project_id: number;
    order_id: number;
    unit_id: number | null;
    units: {
        id: number;
        number: number;
        title: string;
        size: string;
        color: string;
        state: string;
    }[];
}
export function PublicBagLabel() {
    const [data, setData] = useState<Label | null>(null);
    const [error, setError] = useState('');
    useEffect(() => {
        const token =
            new URLSearchParams(window.location.search).get('token') ?? '';
        const controller = new AbortController();
        void (async () => {
            if (!/^[A-Za-z0-9_-]{43}$/.test(token)) throw new Error('QR');
            return requestJson<Label>(`/production/labels/${token}`, {
                cache: 'no-store',
                signal: controller.signal,
            });
        })()
            .then(setData)
            .catch(() => {
                if (!controller.signal.aborted)
                    setError(
                        'Мешок не найден или нет соединения. Повторите сканирование.',
                    );
            });
        return () => controller.abort();
    }, []);
    return (
        <main
            className={styles.terminal}
            style={{ padding: '24px', minHeight: '100dvh' }}
        >
            <h1>Garment Buro · Мешок</h1>
            {error && <p role="alert">{error}</p>}
            {!data && !error && <p role="status">Загружаем состав…</p>}
            {data && (
                <>
                    <h2>Заказ №{data.order_id}</h2>
                    {data.units.map((u) => (
                        <article className={styles.unit} key={u.id}>
                            <h3>
                                #{u.number} · {u.title}
                            </h3>
                            <p>
                                {u.size} · {u.color}
                            </p>
                            <p>{stateLabels[u.state] ?? u.state}</p>
                        </article>
                    ))}
                    <Link
                        href={`/production?project=${data.project_id}${data.unit_id ? `&unit=${data.unit_id}` : ''}`}
                    >
                        Открыть в терминале сотрудника →
                    </Link>
                </>
            )}
        </main>
    );
}
