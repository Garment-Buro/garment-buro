'use client';
import { useEffect, useRef, useState } from 'react';
import { requestJson } from '@/lib/api/http';
import { type AdminPayout, money } from '@/lib/production/adminTypes';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import styles from './ProductionAdmin.module.css';

export function AdminPayoutReview({
    payout,
    onDone,
    onClose,
}: {
    payout: AdminPayout;
    onDone: () => void;
    onClose: () => void;
}) {
    const [note, setNote] = useState('');
    const [status, setStatus] = useState<'approved' | 'rejected'>(
        payout.status === 'requested' ? 'approved' : 'rejected',
    );
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const locked = useRef(false);
    const run = useProductionAuthStore((state) => state.runAuthenticated);

    useEffect(() => {
        const closeOnEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape' && !busy) onClose();
        };
        window.addEventListener('keydown', closeOnEscape);
        return () => window.removeEventListener('keydown', closeOnEscape);
    }, [busy, onClose]);

    return (
        <div
            className={styles.modalBackdrop}
            role="presentation"
            onMouseDown={(event) => {
                if (event.target === event.currentTarget && !busy) onClose();
            }}
        >
            <form
                className={styles.payoutDialog}
                role="dialog"
                aria-modal="true"
                aria-labelledby="payout-review-title"
                onSubmit={async (event) => {
                    event.preventDefault();
                    if (locked.current) return;
                    locked.current = true;
                    setBusy(true);
                    setError('');
                    try {
                        await run(() =>
                            requestJson(
                                `/production/admin/payouts/${payout.id}/review`,
                                {
                                    method: 'POST',
                                    headers: {
                                        'Content-Type': 'application/json',
                                    },
                                    body: JSON.stringify({
                                        expected_status: payout.status,
                                        status,
                                        note: note.trim(),
                                    }),
                                },
                            ),
                        );
                        onDone();
                    } catch (failure) {
                        setError(
                            `${failure instanceof Error ? failure.message : 'Ошибка сохранения'}. При потере связи сначала обновите список и проверьте результат.`,
                        );
                    } finally {
                        locked.current = false;
                        setBusy(false);
                    }
                }}
            >
                <div className={styles.sectionHeading}>
                    <h2 id="payout-review-title">
                        Заявка №{payout.id} · {money(payout.amount)}
                    </h2>
                    <button type="button" disabled={busy} onClick={onClose}>
                        Закрыть
                    </button>
                </div>
                <p>{payout.partner}</p>
                <p>
                    Это решение по заявке. Одобрение не переводит деньги и не
                    подписывает платёж в банке.
                </p>
                <label>
                    Решение
                    <select
                        disabled={busy}
                        value={status}
                        onChange={(event) =>
                            setStatus(
                                event.target.value as 'approved' | 'rejected',
                            )
                        }
                    >
                        {payout.status === 'requested' && (
                            <option value="approved">Одобрить</option>
                        )}
                        <option value="rejected">Отклонить</option>
                    </select>
                </label>
                <label>
                    Комментарий
                    <textarea
                        disabled={busy}
                        required
                        minLength={3}
                        maxLength={500}
                        value={note}
                        onChange={(event) => setNote(event.target.value)}
                    />
                </label>
                {error && (
                    <p role="alert" className={styles.error}>
                        {error}
                    </p>
                )}
                <div className={styles.editorActions}>
                    <button
                        className={styles.primaryButton}
                        type="submit"
                        disabled={busy || note.trim().length < 3}
                    >
                        {busy ? 'Сохраняем…' : 'Подтвердить решение'}
                    </button>
                </div>
            </form>
        </div>
    );
}
