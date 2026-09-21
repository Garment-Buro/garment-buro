'use client';
import { useEffect } from 'react';
import {
    PiEnvelope,
    PiPackage,
    PiPhone,
    PiUserCircle,
    PiX,
} from 'react-icons/pi';
import { type AdminClient, date, money } from '@/lib/production/adminTypes';
import styles from './ProductionAdmin.module.css';

export function AdminClientDetails({
    client,
    onOrder,
    onClose,
}: {
    client: AdminClient;
    onOrder: (id: number) => void;
    onClose: () => void;
}) {
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
                className={styles.clientDialog}
                role="dialog"
                aria-modal="true"
                aria-labelledby="client-details-title"
            >
                <div className={styles.dialogHeading}>
                    <div>
                        <span className={styles.eyebrow}>КЛИЕНТ</span>
                        <h2 id="client-details-title">
                            {client.name || 'Имя не указано'}
                        </h2>
                    </div>
                    <button
                        type="button"
                        className={styles.iconButton}
                        aria-label="Закрыть данные клиента"
                        title="Закрыть"
                        onClick={onClose}
                    >
                        <PiX aria-hidden />
                    </button>
                </div>
                <div className={styles.clientContactList}>
                    <p>
                        <PiUserCircle aria-hidden />
                        <span>
                            <small>Тип клиента</small>
                            <strong>
                                {client.user_id
                                    ? `Аккаунт №${client.user_id}`
                                    : 'Гостевые заказы'}
                            </strong>
                        </span>
                    </p>
                    <p>
                        <PiEnvelope aria-hidden />
                        <span>
                            <small>Почта</small>
                            <strong>{client.email || 'Не указана'}</strong>
                        </span>
                    </p>
                    <p>
                        <PiPhone aria-hidden />
                        <span>
                            <small>Телефон</small>
                            <strong>{client.phone || 'Не указан'}</strong>
                        </span>
                    </p>
                </div>
                <dl className={styles.clientTotals}>
                    <div>
                        <dt>Заказов</dt>
                        <dd>{client.orders_count}</dd>
                    </div>
                    <div>
                        <dt>Сумма заказов</dt>
                        <dd>{money(client.orders_total)}</dd>
                    </div>
                    <div>
                        <dt>Оплачено</dt>
                        <dd>{money(client.paid_orders_total)}</dd>
                    </div>
                </dl>
                <button
                    type="button"
                    className={styles.primaryButton}
                    onClick={() => onOrder(client.last_order_id)}
                >
                    <PiPackage aria-hidden />
                    Последний заказ №{client.last_order_id} ·{' '}
                    {date(client.last_order_at)}
                </button>
            </section>
        </div>
    );
}
