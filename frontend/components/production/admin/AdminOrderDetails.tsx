'use client';
import { useEffect, useState } from 'react';
import {
    PiArrowClockwise,
    PiCheckCircle,
    PiMapPin,
    PiPackage,
    PiUserCircle,
    PiWarningCircle,
    PiX,
} from 'react-icons/pi';
import { CreateTicket } from '@/components/support/CreateTicket';
import { TicketConversation } from '@/components/support/TicketConversation';
import { useAdminResource } from '@/hooks/production/useAdminResource';
import {
    type AdminOrder,
    type AdminOrderDetail,
    date,
    money,
    statusLabels,
} from '@/lib/production/adminTypes';
import { labels, stateLabels } from '@/lib/production/types';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import { AdminOrderItem } from './AdminOrderItem';
import styles from './ProductionAdmin.module.css';

export function AdminOrderDetails({
    id,
    onClient,
    onClose,
}: {
    id: number;
    onClient: (order: AdminOrder) => void;
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
                <div
                    className={`${styles.dialogHeading} ${styles.orderDialogHeading}`}
                >
                    <div>
                        <span className={styles.eyebrow}>ЗАКАЗ</span>
                        <h2 id="admin-order-title">№{id}</h2>
                    </div>
                    <div className={styles.dialogActions}>
                        <button
                            type="button"
                            className={styles.iconButton}
                            aria-label="Обновить заказ"
                            title="Обновить заказ"
                            disabled={loading}
                            onClick={reload}
                        >
                            <PiArrowClockwise aria-hidden />
                        </button>
                        <button
                            type="button"
                            className={styles.iconButton}
                            aria-label="Закрыть заказ"
                            title="Закрыть"
                            onClick={onClose}
                        >
                            <PiX aria-hidden />
                        </button>
                    </div>
                </div>
                {loading && (
                    <div className={styles.orderSkeleton} role="status">
                        <span>Загружаем заказ…</span>
                        <i />
                        <i />
                        <i />
                    </div>
                )}
                {error && (
                    <div className={styles.error} role="alert">
                        <p>{error}</p>
                        <button
                            type="button"
                            className={styles.iconButton}
                            aria-label="Повторить загрузку заказа"
                            title="Повторить"
                            onClick={reload}
                        >
                            <PiArrowClockwise aria-hidden />
                        </button>
                    </div>
                )}
                {data && (
                    <div className={styles.orderDetailsBody}>
                        <section className={styles.orderOverview}>
                            <button
                                type="button"
                                className={styles.customerLink}
                                onClick={() => onClient(data)}
                            >
                                <PiUserCircle aria-hidden />
                                <span>
                                    <small>Клиент</small>
                                    <strong>
                                        {data.name || 'Имя не указано'}
                                    </strong>
                                    <small>
                                        {[data.email, data.phone]
                                            .filter(Boolean)
                                            .join(' · ') ||
                                            'Контакты не указаны'}
                                    </small>
                                </span>
                            </button>
                            <dl className={styles.orderSummary}>
                                <div>
                                    <dt>Создан</dt>
                                    <dd>{date(data.created_at)}</dd>
                                </div>
                                <div>
                                    <dt>Этап</dt>
                                    <dd>
                                        {statusLabels[
                                            data.workflow_state || data.status
                                        ] || data.status}
                                    </dd>
                                </div>
                                <div>
                                    <dt>Оплата</dt>
                                    <dd>
                                        {statusLabels[data.payment_status] ||
                                            data.payment_status}
                                    </dd>
                                </div>
                                <div>
                                    <dt>Итого</dt>
                                    <dd>{money(data.total)}</dd>
                                </div>
                            </dl>
                        </section>

                        <section className={styles.orderInfoCard}>
                            <div className={styles.orderSectionHeading}>
                                <PiMapPin aria-hidden />
                                <h3>Доставка</h3>
                            </div>
                            <p>
                                {[
                                    data.delivery_city,
                                    data.delivery_address,
                                    data.pickup_point &&
                                        `Пункт ${data.pickup_point}`,
                                ]
                                    .filter(Boolean)
                                    .join(', ') || 'Адрес не сохранён'}
                            </p>
                            <small>
                                {data.delivery_method || 'Способ не указан'} ·{' '}
                                {money(data.delivery_price)}
                            </small>
                        </section>

                        <section className={styles.orderInfoCard}>
                            <div className={styles.orderSectionHeading}>
                                <PiPackage aria-hidden />
                                <h3>Производство</h3>
                            </div>
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
                                            {data.production.tech_approved ? (
                                                <PiCheckCircle aria-hidden />
                                            ) : (
                                                <PiWarningCircle aria-hidden />
                                            )}
                                            <small>Технолог</small>
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
                                            {data.production.dtf_approved ? (
                                                <PiCheckCircle aria-hidden />
                                            ) : (
                                                <PiWarningCircle aria-hidden />
                                            )}
                                            <small>DTF</small>
                                            <strong>
                                                {data.production.dtf_approved
                                                    ? 'Подтвердил'
                                                    : 'Ожидается'}
                                            </strong>
                                        </span>
                                        <span
                                            data-ready={data.production.qr_ready}
                                        >
                                            {data.production.qr_ready ? (
                                                <PiCheckCircle aria-hidden />
                                            ) : (
                                                <PiWarningCircle aria-hidden />
                                            )}
                                            <small>QR заказа</small>
                                            <strong>
                                                {data.production.qr_ready
                                                    ? 'Доступен'
                                                    : 'Заблокирован'}
                                            </strong>
                                        </span>
                                    </div>
                                    <div className={styles.productionUnitList}>
                                        {data.production.units.map((unit) => (
                                            <div key={unit.id}>
                                                <span>
                                                    <strong>
                                                        Вещь №{unit.number}
                                                    </strong>
                                                    <small>
                                                        {unit.source.title}
                                                    </small>
                                                </span>
                                                <span>
                                                    {unit.lane &&
                                                    unit.lane in labels
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
                                                          data.production
                                                              ?.state ||
                                                          'В очереди'}
                                                </span>
                                                {unit.issue && (
                                                    <small
                                                        className={
                                                            styles.errorText
                                                        }
                                                    >
                                                        {unit.issue}
                                                    </small>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                </>
                            ) : (
                                <p>Заказ ещё не передан в производство.</p>
                            )}
                        </section>

                        <section className={styles.orderComposition}>
                            <div className={styles.orderSectionHeading}>
                                <PiPackage aria-hidden />
                                <div>
                                    <h3>Состав заказа</h3>
                                    <small>
                                        {data.items.length}{' '}
                                        {data.items.length === 1
                                            ? 'позиция'
                                            : 'позиций'}
                                    </small>
                                </div>
                            </div>
                            <div className={styles.orderItemList}>
                                {data.items.map((item) => (
                                    <AdminOrderItem key={item.id} item={item} />
                                ))}
                            </div>
                        </section>

                        {systemAdmin && (
                            <details className={styles.orderSupport}>
                                <summary>Связаться с клиентом</summary>
                                <CreateTicket
                                    admin
                                    orderId={id}
                                    onCreated={setTicketId}
                                />
                            </details>
                        )}
                        {ticketId !== null && (
                            <TicketConversation
                                key={ticketId}
                                id={ticketId}
                                mode="admin"
                            />
                        )}
                    </div>
                )}
            </section>
        </div>
    );
}
