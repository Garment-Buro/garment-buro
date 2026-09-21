'use client';

import { useState } from 'react';
import { TicketConversation } from '@/components/support/TicketConversation';
import { useAdminResource } from '@/hooks/production/useAdminResource';
import { requestJson } from '@/lib/api/http';
import {
    type AdminInboxItem,
    type AdminInboxPriority,
    type AdminInboxStatus,
    type AdminSection,
    date,
    priorityLabels,
    stationLabels,
    statusLabels,
} from '@/lib/production/adminTypes';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import styles from './ProductionAdmin.module.css';

type InboxSection = Extract<AdminSection, 'problems' | 'support'>;

function InboxForm({
    item,
    section,
    onSaved,
}: {
    item: AdminInboxItem;
    section: InboxSection;
    onSaved: () => void;
}) {
    const currentUser = useProductionAuthStore((state) => state.user);
    const run = useProductionAuthStore((state) => state.runAuthenticated);
    const [status, setStatus] = useState<AdminInboxStatus>(item.status);
    const [priority, setPriority] = useState<AdminInboxPriority>(item.priority);
    const [assignee, setAssignee] = useState(
        item.assigned_to_user_id ? String(item.assigned_to_user_id) : '',
    );
    const [note, setNote] = useState(item.admin_note || '');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');

    return (
        <form
            onSubmit={async (event) => {
                event.preventDefault();
                if (busy) return;
                setBusy(true);
                setError('');
                try {
                    await run(() =>
                        requestJson<AdminInboxItem>(
                            `/production/admin/${section}/${item.id}`,
                            {
                                method: 'PATCH',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    expected_version: item.version,
                                    status,
                                    priority,
                                    assigned_to_user_id: assignee
                                        ? Number(assignee)
                                        : null,
                                    admin_note: note.trim() || null,
                                }),
                            },
                        ),
                    );
                    onSaved();
                } catch (failure) {
                    setError(
                        failure instanceof Error
                            ? failure.message
                            : 'Не удалось сохранить обращение',
                    );
                } finally {
                    setBusy(false);
                }
            }}
        >
            <div className={styles.inboxContext}>
                <div>
                    <small>Автор</small>
                    <strong>{item.reporter_name || 'Не указан'}</strong>
                    <small>
                        {[item.reporter_email, item.reporter_phone]
                            .filter(Boolean)
                            .join(' · ') || 'Контактов нет'}
                    </small>
                </div>
                <div>
                    <small>Создано</small>
                    <strong>{date(item.created_at)}</strong>
                    <small>Версия {item.version}</small>
                </div>
                {section === 'support' ? (
                    <div>
                        <small>Заказ</small>
                        <strong>
                            {item.order_id ? `№${item.order_id}` : 'Не указан'}
                        </strong>
                    </div>
                ) : (
                    <div>
                        <small>Производство</small>
                        <strong>
                            {item.station && item.station in stationLabels
                                ? stationLabels[
                                      item.station as keyof typeof stationLabels
                                  ]
                                : 'Участок не указан'}
                        </strong>
                        <small>
                            {[
                                item.project_id && `Проект №${item.project_id}`,
                                item.production_unit_id &&
                                    `Единица №${item.production_unit_id}`,
                            ]
                                .filter(Boolean)
                                .join(' · ') || 'Без привязки к проекту'}
                        </small>
                    </div>
                )}
            </div>

            <article className={styles.inboxMessage}>
                <h3>{item.subject}</h3>
                <p>{item.message}</p>
            </article>

            <fieldset className={styles.formSection}>
                <legend>Обработка обращения</legend>
                <div className={styles.formGrid}>
                    <label>
                        Статус
                        <select
                            disabled={busy}
                            value={status}
                            onChange={(event) =>
                                setStatus(event.target.value as AdminInboxStatus)
                            }
                        >
                            {(['new', 'in_progress', 'resolved', 'closed'] as const).map(
                                (value) => (
                                    <option key={value} value={value}>
                                        {statusLabels[value]}
                                    </option>
                                ),
                            )}
                        </select>
                    </label>
                    <label>
                        Приоритет
                        <select
                            disabled={busy}
                            value={priority}
                            onChange={(event) =>
                                setPriority(
                                    event.target.value as AdminInboxPriority,
                                )
                            }
                        >
                            {(
                                ['low', 'normal', 'high', 'critical'] as const
                            ).map((value) => (
                                <option key={value} value={value}>
                                    {priorityLabels[value]}
                                </option>
                            ))}
                        </select>
                    </label>
                </div>
                <label className={styles.assigneeField}>
                    Ответственный
                    <select
                        disabled={busy}
                        value={assignee}
                        onChange={(event) => setAssignee(event.target.value)}
                    >
                        <option value="">Без ответственного</option>
                        {item.assigned_to_user_id &&
                            item.assigned_to_user_id !== currentUser?.id && (
                                <option value={item.assigned_to_user_id}>
                                    Администратор №{item.assigned_to_user_id}
                                </option>
                            )}
                        {currentUser && (
                            <option value={currentUser.id}>Назначить на меня</option>
                        )}
                    </select>
                </label>
                <label>
                    Внутренний комментарий
                    <textarea
                        disabled={busy}
                        maxLength={5000}
                        placeholder="Что проверили и что нужно сделать дальше"
                        value={note}
                        onChange={(event) => setNote(event.target.value)}
                    />
                    <small>Пользователь и сотрудник этот комментарий не увидят.</small>
                </label>
            </fieldset>

            {error && (
                <p role="alert" className={styles.error}>
                    {error}
                </p>
            )}
            <div className={styles.editorActions}>
                <button
                    className={styles.primaryButton}
                    type="submit"
                    disabled={busy}
                >
                    {busy ? 'Сохраняем…' : 'Сохранить изменения'}
                </button>
            </div>
        </form>
    );
}

export function AdminInboxDetails({
    section,
    id,
    onClose,
    onSaved,
}: {
    section: InboxSection;
    id: number;
    onClose: () => void;
    onSaved: () => void;
}) {
    const { data, loading, error, reload } = useAdminResource<AdminInboxItem>(
        `${section}/${id}`,
    );
    return (
        <div className={styles.modalBackdrop} role="presentation">
            <section
                className={styles.inboxDialog}
                role="dialog"
                aria-modal="true"
                aria-labelledby="inbox-dialog-title"
                aria-busy={loading}
            >
                <div className={styles.sectionHeading}>
                    <div>
                        <p className={styles.eyebrow}>
                            {section === 'support'
                                ? 'СООБЩЕНИЕ В ПОДДЕРЖКУ'
                                : 'ПРОБЛЕМА НА ПРОИЗВОДСТВЕ'}
                        </p>
                        <h2 id="inbox-dialog-title">Обращение №{id}</h2>
                    </div>
                    <button type="button" onClick={onClose}>
                        Закрыть
                    </button>
                </div>
                {loading && <p role="status">Загружаем обращение…</p>}
                {error && (
                    <div>
                        <p role="alert" className={styles.error}>
                            {error}
                        </p>
                        <button type="button" onClick={reload}>
                            Повторить
                        </button>
                    </div>
                )}
                {data && (
                    <>
                    <TicketConversation id={id} mode="admin" onChanged={reload} />
                    <InboxForm
                        key={data.version}
                        item={data}
                        section={section}
                        onSaved={() => { reload(); onSaved(); }}
                    />
                    </>
                )}
            </section>
        </div>
    );
}
