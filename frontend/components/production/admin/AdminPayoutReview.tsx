'use client';
import { useEffect, useRef, useState } from 'react';
import { PiBank, PiCalendar, PiUserCircle, PiWallet, PiX } from 'react-icons/pi';
import { requestJson } from '@/lib/api/http';
import {
    type AdminPayout,
    date,
    money,
    statusLabels,
} from '@/lib/production/adminTypes';
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
    const [note, setNote] = useState(payout.note || '');
    const [status, setStatus] = useState<'approved' | 'rejected'>(
        payout.status === 'requested' ? 'approved' : 'rejected',
    );
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const locked = useRef(false);
    const run = useProductionAuthStore((state) => state.runAuthenticated);
    const canReview =
        !payout.bank_state && ['requested', 'approved'].includes(payout.status);

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
                    if (locked.current || !canReview) return;
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
                <div className={styles.dialogHeading}>
                    <div>
                        <span className={styles.eyebrow}>ЗАЯВКА НА ВЫПЛАТУ</span>
                        <h2 id="payout-review-title">№{payout.id}</h2>
                    </div>
                    <button
                        type="button"
                        className={styles.iconButton}
                        aria-label="Закрыть заявку"
                        title="Закрыть"
                        disabled={busy}
                        onClick={onClose}
                    >
                        <PiX aria-hidden />
                    </button>
                </div>

                <div className={styles.payoutSummary}>
                    <p className={styles.payoutAmount}>
                        <PiWallet aria-hidden />
                        <span>
                            <small>Сумма выплаты</small>
                            <strong>{money(payout.amount)}</strong>
                        </span>
                    </p>
                    <dl>
                        <div>
                            <dt>
                                <PiUserCircle aria-hidden /> Партнёр
                            </dt>
                            <dd>{payout.partner}</dd>
                        </div>
                        <div>
                            <dt>
                                <PiCalendar aria-hidden /> Создана
                            </dt>
                            <dd>{date(payout.created_at)}</dd>
                        </div>
                        <div>
                            <dt>
                                <PiBank aria-hidden /> Состояние
                            </dt>
                            <dd>
                                {statusLabels[payout.status] || payout.status}
                            </dd>
                        </div>
                    </dl>
                </div>

                {canReview ? (
                    <>
                        <p className={styles.payoutNotice}>
                            Решение меняет статус заявки, но не переводит деньги
                            и не подписывает платёж в банке.
                        </p>
                        <div className={styles.payoutFormGrid}>
                            <label>
                                Решение
                                <select
                                    disabled={busy}
                                    value={status}
                                    onChange={(event) =>
                                        setStatus(
                                            event.target.value as
                                                | 'approved'
                                                | 'rejected',
                                        )
                                    }
                                >
                                    {payout.status === 'requested' && (
                                        <option value="approved">
                                            Одобрить
                                        </option>
                                    )}
                                    <option value="rejected">Отклонить</option>
                                </select>
                            </label>
                            <label>
                                Комментарий к решению
                                <textarea
                                    disabled={busy}
                                    required
                                    minLength={3}
                                    maxLength={500}
                                    rows={4}
                                    placeholder="Почему заявка одобрена или отклонена"
                                    value={note}
                                    onChange={(event) =>
                                        setNote(event.target.value)
                                    }
                                />
                            </label>
                        </div>
                    </>
                ) : (
                    <div className={styles.payoutNotice}>
                        <strong>Заявка доступна только для просмотра</strong>
                        <p>
                            {payout.bank_state
                                ? `Состояние в банке: ${statusLabels[payout.bank_state] || payout.bank_state}.`
                                : 'Решение по этой заявке уже завершено.'}
                        </p>
                        {payout.note && <p>Комментарий: {payout.note}</p>}
                    </div>
                )}
                {error && (
                    <p role="alert" className={styles.error}>
                        {error}
                    </p>
                )}
                {canReview && (
                    <div className={styles.editorActions}>
                        <button
                            type="button"
                            disabled={busy}
                            onClick={onClose}
                        >
                            Отмена
                        </button>
                        <button
                            className={styles.primaryButton}
                            type="submit"
                            disabled={busy || note.trim().length < 3}
                        >
                            {busy ? 'Сохраняем…' : 'Подтвердить решение'}
                        </button>
                    </div>
                )}
            </form>
        </div>
    );
}
