'use client';
import { useEffect, useState } from 'react';
import { CreateTicket } from '@/components/support/CreateTicket';
import { TicketConversation } from '@/components/support/TicketConversation';
import { useAdminResource } from '@/hooks/production/useAdminResource';
import {
    type AdminOrderDetail,
    date,
    money,
    statusLabels,
} from '@/lib/production/adminTypes';
import { labels, stateLabels } from '@/lib/production/types';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import styles from './ProductionAdmin.module.css';

export function AdminOrderDetails({
    id,
    onClose,
}: {
    id: number;
    onClose: () => void;
}) {
    const [ticketId, setTicketId] = useState<number | null>(null);
    const systemAdmin = useProductionAuthStore(
        (state) => state.user?.admin_scope === 'system',
    );
    const { data, loading, error, reload } = useAdminResource<AdminOrderDetail>(
        `orders/${id}`,
    );

    useEffect(() => {
        const closeOnEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', closeOnEscape);
        return () => window.removeEventListener('keydown', closeOnEscape);
    }, [onClose]);

    return (
        <div
            className={styles.modalBackdrop}
            role="presentation"
            onMouseDown={(event) => {
                if (event.target === event.currentTarget) onClose();
            }}
        >
            <section
                className={styles.orderDialog}
                role="dialog"
                aria-modal="true"
                aria-labelledby="admin-order-title"
                aria-busy={loading}
            >
                <div className={styles.sectionHeading}>
                    <h2 id="admin-order-title">Заказ №{id}</h2>
                    <button type="button" onClick={onClose}>
                        Закрыть
                    </button>
                </div>
                {loading && <p role="status">Загружаем состав заказа…</p>}
                {error && (
                    <>
                        <p role="alert" className={styles.error}>
                            {error}
                        </p>
                        <button onClick={reload}>Повторить</button>
                    </>
                )}
                {data && (
                    <>
                        {systemAdmin && (
                            <CreateTicket
                                admin
                                orderId={id}
                                onCreated={setTicketId}
                            />
                        )}
                        {ticketId !== null && <TicketConversation key={ticketId} id={ticketId} mode="admin" />}
                        <p>
                            {data.name || 'Имя не указано'} ·{' '}
                            {data.email || 'Без почты'} ·{' '}
                            {data.phone || 'Без телефона'}
                        </p>
                        <p>
                            {date(data.created_at)} ·{' '}
                            {statusLabels[
                                data.workflow_state || data.status
                            ] || data.status}{' '}
                            · {money(data.total)}
                        </p>
                        <h3>Доставка</h3>
                        <p>
                            {[
                                data.delivery_city,
                                data.delivery_address,
                                data.pickup_point,
                            ]
                                .filter(Boolean)
                                .join(', ') || 'Адрес не сохранён'}
                        </p>
                        <p>
                            {data.delivery_method || 'Способ не указан'} ·{' '}
                            {money(data.delivery_price)}
                        </p>
                        <h3>Производство</h3>
                        {data.production ? (
                            <>
                                <p>
                                    Проект №{data.production.project_id} ·{' '}
                                    {stateLabels[
                                        data.production.display_state ||
                                            data.production.state
                                    ] || data.production.state}
                                </p>
                                <div className={styles.approvalGrid}>
                                    <span
                                        data-ready={
                                            data.production.tech_approved
                                        }
                                    >
                                        Технолог
                                        <strong>
                                            {data.production.tech_approved
                                                ? 'Подтвердил'
                                                : 'Ожидается'}
                                        </strong>
                                    </span>
                                    <span
                                        data-ready={
                                            data.production.dtf_approved
                                        }
                                    >
                                        DTF
                                        <strong>
                                            {data.production.dtf_approved
                                                ? 'Подтвердил'
                                                : 'Ожидается'}
                                        </strong>
                                    </span>
                                    <span data-ready={data.production.qr_ready}>
                                        QR заказа
                                        <strong>
                                            {data.production.qr_ready
                                                ? 'Доступен'
                                                : 'Заблокирован'}
                                        </strong>
                                    </span>
                                </div>
                                {data.production.units.map((unit) => (
                                    <article
                                        key={unit.id}
                                        className={styles.item}
                                    >
                                        <h4>
                                            Вещь №{unit.number} ·{' '}
                                            {unit.source.title}
                                        </h4>
                                        <p>
                                            Этап:{' '}
                                            {unit.lane && unit.lane in labels
                                                ? labels[
                                                      unit.lane as keyof typeof labels
                                                  ]
                                                : stateLabels[
                                                      unit.lane ||
                                                          data.production
                                                              ?.state ||
                                                          'inbox'
                                                  ] ||
                                                  unit.lane ||
                                                  data.production?.state ||
                                                  'inbox'}
                                        </p>
                                        {unit.issue && (
                                            <p className={styles.error}>
                                                Проблема: {unit.issue}
                                            </p>
                                        )}
                                    </article>
                                ))}
                            </>
                        ) : (
                            <p>Заказ ещё не передан в производство.</p>
                        )}
                        <h3>Состав заказа</h3>
                        {data.items.map((item) => (
                            <article key={item.id} className={styles.item}>
                                <h4>
                                    {item.title} · {item.quantity} шт.
                                </h4>
                                <p>
                                    {item.size} · {item.color} ·{' '}
                                    {money(item.total)}
                                </p>
                                {item.customization && (
                                    <details>
                                        <summary>
                                            Сохранённые параметры конструктора
                                        </summary>
                                        <pre>
                                            {JSON.stringify(
                                                item.customization,
                                                null,
                                                2,
                                            )}
                                        </pre>
                                    </details>
                                )}
                            </article>
                        ))}
                    </>
                )}
            </section>
        </div>
    );
}
