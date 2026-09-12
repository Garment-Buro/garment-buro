'use client';
import { useRef, useState } from 'react';
import { requestJson } from '@/lib/api/http';
import type { AdminOrderDetail } from '@/lib/production/adminTypes';
import styles from './ProductionAdmin.module.css';

export function AdminOrderModeration({
    order,
    reload,
}: {
    order: AdminOrderDetail;
    reload: () => void;
}) {
    const [note, setNote] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const pending = useRef<{
        key: string;
        decision: string;
        note: string;
        version: number;
    } | null>(null);
    const flow = order.moderation;
    if (!flow) return null;
    async function decide(decision: 'approve' | 'reject') {
        if (busy || !flow) return;
        setBusy(true);
        setError('');
        const command = pending.current ?? {
            key: crypto.randomUUID(),
            decision,
            note: note.trim(),
            version: flow.version,
        };
        pending.current = command;
        try {
            await requestJson(
                `/production/admin/orders/${order.id}/moderation`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Idempotency-Key': command.key,
                    },
                    body: JSON.stringify({
                        expected_version: command.version,
                        decision: command.decision,
                        note: command.note,
                    }),
                },
            );
            pending.current = null;
            reload();
        } catch (e) {
            setError(
                e instanceof Error
                    ? e.message
                    : 'Не удалось подтвердить решение',
            );
        } finally {
            setBusy(false);
        }
    }
    return (
        <section className={styles.card}>
            <h3>Модерация и холд ЮKassa</h3>
            <p>
                Состояние: {flow.state}
                {flow.hold_expires_at
                    ? ` · Холд до ${new Date(flow.hold_expires_at).toLocaleString('ru-RU')}`
                    : ''}
            </p>
            {flow.attention && (
                <p role="alert">Требует проверки: {flow.attention}</p>
            )}
            {flow.state === 'moderation' && (
                <>
                    <p>
                        Подтверждение запускает списание удержанных средств.
                        Технолог получит заказ после подтверждения оплаты
                        ЮKassa. Отклонение отменяет холд.
                    </p>
                    <label>
                        Решение по заказу
                        <textarea
                            value={note}
                            maxLength={2000}
                            disabled={busy || !!pending.current}
                            onChange={(e) => setNote(e.target.value)}
                        />
                    </label>
                    <button
                        disabled={
                            busy ||
                            !note.trim() ||
                            Boolean(
                                pending.current &&
                                    pending.current.decision !== 'approve',
                            )
                        }
                        onClick={() => void decide('approve')}
                    >
                        Можем выполнить — подтвердить и списать
                    </button>
                    <button
                        disabled={
                            busy ||
                            !note.trim() ||
                            Boolean(
                                pending.current &&
                                    pending.current.decision !== 'reject',
                            )
                        }
                        onClick={() => void decide('reject')}
                    >
                        Отклонить и отменить холд
                    </button>
                </>
            )}
            {['capture_pending', 'cancel_pending'].includes(flow.state) && (
                <p>Решение сохранено. Ожидаем подтверждение ЮKassa.</p>
            )}
            {error && <p role="alert">{error}</p>}
        </section>
    );
}
